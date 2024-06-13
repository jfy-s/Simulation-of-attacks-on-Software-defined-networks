from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.revent import *
from pox.openflow.discovery import Discovery
from pox.lib.addresses import IPAddr, EthAddr
import networkx as nx
from pox.lib.packet.arp import arp
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.ipv4 import ipv4
from pox.lib.recoco import Timer

log = core.getLogger()

class SimpleController(EventMixin):
    def __init__(self):
        self.topology = nx.Graph()
        self.mac_to_port = {}  # dpid -> mac -> port
        self.arp_table = {}    # ip -> mac
        self.hosts = {}        # ip -> (dpid, port)
        self.switches = {}     # dpid -> connection

        core.openflow.addListeners(self)
        core.openflow_discovery.addListeners(self)

        # Start a timer to log network state periodically
        Timer(10, self._log_network_state, recurring=True)
        
    def _handle_ConnectionUp(self, event):
        dpid = event.dpid
        self.switches[dpid] = event.connection
        self.mac_to_port[dpid] = {}
        log.info(f"Switch {dpid} connected")

    def _handle_LinkEvent(self, event):
        link = event.link
        if event.added:
            self.topology.add_edge(link.dpid1, link.dpid2, port=(link.port1, link.port2))
            log.info(f"Link added: {link.dpid1} <-> {link.dpid2}")
        elif event.removed:
            if self.topology.has_edge(link.dpid1, link.dpid2):
                self.topology.remove_edge(link.dpid1, link.dpid2)
                log.info(f"Link removed: {link.dpid1} <-> {link.dpid2}")
            else:
                log.warning(f"Tried to remove non-existent link: {link.dpid1} <-> {link.dpid2}")

    def _handle_PacketIn(self, event):
        packet = event.parsed
        dpid = event.dpid
        in_port = event.port

        if dpid not in self.mac_to_port:
            self.mac_to_port[dpid] = {}

        self.mac_to_port[dpid][packet.src] = in_port

        if packet.type == ethernet.ARP_TYPE:
            arp_packet = packet.next
            self.arp_table[arp_packet.protosrc] = packet.src
            self.hosts[arp_packet.protosrc] = (dpid, in_port)
            log.info(f"Discovered host {arp_packet.protosrc} at {dpid}:{in_port}")
            self._handle_arp(event, packet, arp_packet)
        elif packet.type == ethernet.IP_TYPE:
            ip_packet = packet.next
            self.hosts[ip_packet.srcip] = (dpid, in_port)
            log.info(f"Discovered host {ip_packet.srcip} at {dpid}:{in_port}")
            self._handle_ip(event, packet, ip_packet)
        else:
            self._flood(event)

    def _handle_arp(self, event, packet, arp_packet):
        if arp_packet.opcode == arp.REQUEST:
            if arp_packet.protodst in self.arp_table:
                self._send_arp_reply(event, packet, arp_packet)
            else:
                self._flood(event)
        elif arp_packet.opcode == arp.REPLY:
            self._forward_packet(event, packet)

    def _send_arp_reply(self, event, packet, arp_packet):
        arp_reply = arp()
        arp_reply.hwsrc = self.arp_table[arp_packet.protodst]
        arp_reply.hwdst = packet.src
        arp_reply.opcode = arp.REPLY
        arp_reply.protosrc = arp_packet.protodst
        arp_reply.protodst = arp_packet.protosrc

        ether = ethernet()
        ether.src = arp_reply.hwsrc
        ether.dst = arp_reply.hwdst
        ether.type = ethernet.ARP_TYPE
        ether.payload = arp_reply

        msg = of.ofp_packet_out()
        msg.data = ether.pack()
        msg.actions.append(of.ofp_action_output(port=event.port))
        self.switches[event.dpid].send(msg)
        log.info(f"Sent ARP reply from {arp_reply.protosrc} to {arp_reply.protodst} on switch {event.dpid}")

    def _handle_ip(self, event, packet, ip_packet):
        src_ip = str(ip_packet.srcip)
        dst_ip = str(ip_packet.dstip)

        if dst_ip in self.arp_table:
            dst_mac = self.arp_table[dst_ip]
            dst_host = self.hosts[dst_ip]
            path = self._get_path(event.dpid, dst_host[0])

            if path:
                self._install_path(event, path, packet.src, packet.dst, dst_host[1])
                self._send_packet(event, packet, self.mac_to_port[event.dpid].get(dst_mac, of.OFPP_FLOOD))
                log.info(f"Forwarded IP packet from {src_ip} to {dst_ip} on switch {event.dpid} via port {self.mac_to_port[event.dpid].get(dst_mac, of.OFPP_FLOOD)}")
            else:
                self._flood(event)
        else:
            self._flood(event)

    def _get_path(self, src, dst):
        try:
            path = nx.shortest_path(self.topology, src, dst)
            log.info(f"Path from {src} to {dst}: {path}")
            return path
        except nx.NetworkXNoPath:
            log.warning(f"No path found from {src} to {dst}")
            return None

    def _install_path(self, event, path, src_mac, dst_mac, dst_port):
        for i in range(len(path) - 1):
            node = path[i]
            next_node = path[i + 1]
            port = self.topology[node][next_node]['port'][0]
            match = of.ofp_match()
            match.dl_src = EthAddr(src_mac)
            match.dl_dst = EthAddr(dst_mac)
            actions = [of.ofp_action_output(port=port)]
            self._install_flow(node, match, actions)

        last_node = path[-1]
        match = of.ofp_match()
        match.dl_src = EthAddr(src_mac)
        match.dl_dst = EthAddr(dst_mac)
        actions = [of.ofp_action_output(port=dst_port)]
        self._install_flow(last_node, match, actions)

    def _install_flow(self, dpid, match, actions):
        msg = of.ofp_flow_mod()
        msg.match = match
        msg.actions = actions
        self.switches[dpid].send(msg)
        log.info(f"Installed flow on switch {dpid}: match={match} actions={actions}")

    def _forward_packet(self, event, packet):
        dpid = event.dpid
        in_port = event.port
        out_port = None

        if packet.type == ethernet.ARP_TYPE:
            dst_mac = packet.next.hwdst
        elif packet.type == ethernet.IP_TYPE:
            dst_ip = str(packet.next.dstip)
            dst_mac = self.arp_table.get(dst_ip)

        if dst_mac:
            out_port = self.mac_to_port[dpid].get(dst_mac)

        if out_port is None:
            self._flood(event)
        else:
            self._send_packet(event, packet, out_port)
            log.info(f"Forwarded packet on switch {dpid} from port {in_port} to port {out_port}")

    def _send_packet(self, event, packet, out_port):
        msg = of.ofp_packet_out()
        msg.data = event.ofp
        msg.actions.append(of.ofp_action_output(port=out_port))
        msg.in_port = event.port
        self.switches[event.dpid].send(msg)

    def _flood(self, event):
        msg = of.ofp_packet_out()
        msg.data = event.ofp
        msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
        msg.in_port = event.port
        self.switches[event.dpid].send(msg)
        log.info(f"Flooded packet on switch {event.dpid} from port {event.port}")

    def _log_network_state(self):
        num_switches = len(self.switches)
        num_links = len(self.topology.edges())
        num_hosts = len(self.hosts)
        log.info(f"Network State: {num_switches} switches, {num_links} links, {num_hosts} hosts")

def launch():
    core.registerNew(SimpleController)
