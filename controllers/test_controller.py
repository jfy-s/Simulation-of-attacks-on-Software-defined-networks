# -*- coding: utf-8 -*-
import pox.openflow.libopenflow_01 as of
import pox.lib.packet as pkt
from pox.core import core
from pox.lib.revent import *
from pox.lib.util import dpid_to_str, str_to_dpid
from pox.lib.recoco import Timer

import networkx as nx

log = core.getLogger()

topo = nx.DiGraph()

class DijkstraController(EventMixin):
    def __init__(self):
        self.listenTo(core.openflow)
        core.openflow_discovery.addListeners(self)
        self.mac_to_port = {}
        self.port_stats = {}
        self.update_interval = 5 
        self.bandwidth = 300
        Timer(self.update_interval, self._request_stats, recurring=True)

    def _handle_LinkEvent(self, event):
        link = event.link
        if event.added:
            bandwidth = self.bandwidth
            topo.add_edge(link.dpid1, link.dpid2, port=link.port1, weight=1.0 / bandwidth)
            topo.add_edge(link.dpid2, link.dpid1, port=link.port2, weight=1.0 / bandwidth)
        elif event.removed:
            if topo.has_edge(link.dpid1, link.dpid2):
                topo.remove_edge(link.dpid1, link.dpid2)
            if topo.has_edge(link.dpid2, link.dpid1):
                topo.remove_edge(link.dpid2, link.dpid1)

    def _handle_PacketIn(self, event):
        packet = event.parsed
        dpid = event.dpid
        in_port = event.port

        if packet.type == packet.LLDP_TYPE or packet.type == packet.IPV6_TYPE:
            return

        src = str(packet.src)
        dst = str(packet.dst)

        if src not in self.mac_to_port:
            self.mac_to_port[src] = (dpid, in_port)
        
        if dst in self.mac_to_port:
            dst_dpid, dst_port = self.mac_to_port[dst]
            if dpid in topo.nodes and dst_dpid in topo.nodes:
                try:
                    path = nx.shortest_path(topo, dpid, dst_dpid, weight='weight', method='dijkstra')
                    self.install_path(path, event, dst_port)
                except nx.NetworkXNoPath:
                    log.debug("No path between %s and %s" % (dpid, dst_dpid))
                    self.flood(event)
            else:
                log.debug("DPID %s or %s not in graph" % (dpid, dst_dpid))
                self.flood(event)
        else:
            self.flood(event)

    def install_path(self, path, event, out_port):
        log.debug("Installing path: %s" % str(path))
        for i in range(len(path) - 1):
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match.from_packet(event.parsed, event.port)
            msg.idle_timeout = 300
            msg.hard_timeout = 900
            msg.actions.append(of.ofp_action_output(port=topo[path[i]][path[i+1]]['port']))
            core.openflow.sendToDPID(path[i], msg)
        
        msg = of.ofp_packet_out()
        msg.data = event.ofp
        msg.actions.append(of.ofp_action_output(port=out_port))
        msg.in_port = event.port
        core.openflow.sendToDPID(path[-1], msg)
    
    def flood(self, event):
        msg = of.ofp_packet_out()
        msg.data = event.ofp
        msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
        msg.in_port = event.port
        event.connection.send(msg)

    def _request_stats(self):
        for connection in core.openflow.connections:
            connection.send(of.ofp_stats_request(body=of.ofp_port_stats_request()))

    def _handle_PortStatsReceived(self, event):
        stats = event.stats
        for stat in stats:
            dpid = event.connection.dpid
            port_no = stat.port_no
            tx_bytes = stat.tx_bytes
            rx_bytes = stat.rx_bytes
            bandwidth = self.bandwidth
            available_bandwidth = bandwidth - ((tx_bytes + rx_bytes) / (self.update_interval * 1000.0))
            weight = 1.0 / available_bandwidth if available_bandwidth > 0 else float('inf')
            if dpid in topo:
                for neighbor in topo.neighbors(dpid):
                    if topo[dpid][neighbor]['port'] == port_no:
                        topo[dpid][neighbor]['weight'] = weight

def launch():
    from pox.openflow.discovery import launch as discovery_launch
    from pox.openflow.spanning_tree import launch as stp_launch
    discovery_launch(link_timeout=15, eat_early_packets=True)
    stp_launch()
    core.registerNew(DijkstraController)
