from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.tcp import tcp
from pox.lib.packet.udp import udp
from pox.lib.addresses import IPAddr

log = core.getLogger()

def launch():
    def _handle_ConnectionUp(event):
        log.info("Connection %s" % (event.connection,))
        for port in event.connection.ports:
            msg = of.ofp_flow_mod()
            msg.match.in_port = port
            msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
            event.connection.send(msg)
            log.info(f"Added flow rule to flood packets from port {port}")

    def _handle_PacketIn(event):
        packet = event.parsed

        if packet.type == ethernet.IP_TYPE:
            ip_packet = packet.find('ipv4')
            if ip_packet:
                log.info("Intercepted IP packet: %s -> %s", ip_packet.srcip, ip_packet.dstip)
                if ip_packet.srcip == IPAddr('10.0.0.1') and ip_packet.dstip == IPAddr('10.0.0.5'):
                    original_dst = ip_packet.dstip
                    ip_packet.dstip = IPAddr('10.0.0.3')
                    log.info(f"Modified destination IP from {original_dst} to 10.0.0.3")

                    ip_packet.csum = 0
                    ip_packet.csum = ip_packet.checksum()

                    if isinstance(ip_packet.next, udp):
                        udp_packet = ip_packet.find('udp')
                        udp_packet.csum = 0
                        udp_packet.csum = udp_packet.checksum()
                    elif isinstance(ip_packet.next, tcp):
                        tcp_packet = ip_packet.find('tcp')
                        tcp_packet.csum = 0
                        tcp_packet.csum = tcp_packet.checksum()

                msg = of.ofp_packet_out()
                msg.data = packet.pack()
                msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
                msg.in_port = event.port
                event.connection.send(msg)
                log.info("Sent modified packet")

    core.openflow.addListenerByName("PacketIn", _handle_PacketIn)
    core.openflow.addListenerByName("ConnectionUp", _handle_ConnectionUp)
    log.info("Hijacking Controller script running")
