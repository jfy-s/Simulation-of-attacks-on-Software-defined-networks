from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.link import TCLink
import time

class CustomTopo(Topo):
    def build(self):
        hosts = [self.addHost(f'h{i + 1}') for i in range(5)]
        switches = [self.addSwitch(f's{i + 1}', stp=True) for i in range(5)]
        
        # Switch-to-switch links
        self.addLink(switches[0], switches[1], bw=300, delay=10)
        self.addLink(switches[1], switches[2], bw=300, delay=10)
        self.addLink(switches[2], switches[3], bw=300, delay=10)
        self.addLink(switches[3], switches[4], bw=300, delay=10)

        # Switch-to-host links
        self.addLink(hosts[0], switches[0])
        self.addLink(hosts[1], switches[1])
        self.addLink(hosts[2], switches[2])
        self.addLink(hosts[3], switches[3])
        self.addLink(hosts[4], switches[4])

if __name__ == '__main__':
    setLogLevel('info')

    topo = CustomTopo()
    net = Mininet(topo=topo, link=TCLink, controller=RemoteController)
    net.start()

    # Start iperf servers on all hosts
    hosts = net.hosts
    for host in hosts:
        host.cmd('iperf -s -u &')  # Start iperf server in UDP mode as a daemon

    # Generate traffic with iperf from each host to all other hosts
    
    # for src in hosts:
    #     for dst in hosts:
    #         if src != dst:
    #             src.cmd(f'ping {dst.IP()} -i 0.033 &')
    #             time.sleep(0.1)
    
    # Generate ddos traffic with iperf from first host to all other hosts
    for src in hosts:
        for dst in hosts:
            if src != dst:
                src.cmd(f'iperf -c {dst.IP()} -u -b 10M -t 3600 &')  # 100Mbps for 1 hour
    
    # attacker = hosts[0]
    # for dst in hosts:
    #     if dst != attacker:
    #         attacker.cmd(f'iperf -c {dst.IP()} -u -b 600M -t 3600 &') # 600Mbps for 1 hour
            

    CLI(net)
    net.stop()
