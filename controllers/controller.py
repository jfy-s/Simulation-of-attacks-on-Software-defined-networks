from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.arp import arp
from pox.lib.util import dpidToStr
import time
import csv
import threading

log = core.getLogger()

class PacketCounter:
    def __init__(self):
        self.packet_count = {}
        self.lock = threading.Lock()

    def increment(self, dpid):
        with self.lock:
            if dpid not in self.packet_count:
                self.packet_count[dpid] = 0
            self.packet_count[dpid] += 1

    def get_and_reset(self):
        with self.lock:
            count_copy = self.packet_count.copy()
            self.packet_count = {}
        return count_copy

counter = PacketCounter()

class SimpleSwitch(object):
    def __init__(self, connection):
        self.connection = connection
        self.mac_to_port = {}
        connection.addListeners(self)

    def _handle_PacketIn(self, event):
        packet = event.parsed
        if not packet.parsed:
            log.warning("Ignoring incomplete packet")
            return

        dpid = event.connection.dpid
        in_port = event.port
        counter.increment(dpid)

        self.mac_to_port[packet.src] = in_port

        if packet.dst in self.mac_to_port:
            out_port = self.mac_to_port[packet.dst]
            log.debug("installing flow for %s.%i -> %s.%i" % (packet.src, in_port, packet.dst, out_port))
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match.from_packet(packet, in_port)
            msg.idle_timeout = 10
            msg.hard_timeout = 30
            msg.actions.append(of.ofp_action_output(port = out_port))
            msg.data = event.ofp
            self.connection.send(msg)
        else:
            msg = of.ofp_packet_out()
            msg.data = event.ofp
            msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
            msg.in_port = in_port
            self.connection.send(msg)

class PacketCounterLogger(threading.Thread):
    def __init__(self, interval=1):
        super(PacketCounterLogger, self).__init__()
        self.interval = interval
        self.stop_event = threading.Event()

    def run(self):
        with open('pps_data.csv', 'w', newline='') as csvfile:
            fieldnames = ['timestamp', 'dpid', 'packets_per_second']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            while not self.stop_event.is_set():
                time.sleep(self.interval)
                packet_counts = counter.get_and_reset()
                timestamp = time.time()

                for dpid, count in packet_counts.items():
                    writer.writerow({'timestamp': timestamp, 'dpid': dpid, 'packets_per_second': count})

    def stop(self):
        self.stop_event.set()

logger = PacketCounterLogger()

def start_logger():
    logger.start()

def stop_logger():
    logger.stop()

def launch():
    def start_switch(event):
        log.debug("Controlling %s" % (event.connection,))
        SimpleSwitch(event.connection)

    core.openflow.addListenerByName("ConnectionUp", start_switch)
    core.call_when_ready(start_logger, ['openflow'])
    core.addListenerByName("GoingDownEvent", lambda event: stop_logger())

if __name__ == '__main__':
    launch()
