import networkx as nx
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from time import sleep

class RandomGraphTopo(Topo):
    def build(self, graph, num_hosts=10):
        switches = {}
        
        for node in graph.nodes():
            switches[node] = self.addSwitch(f's{node + 1}')
        
        for (u, v) in graph.edges():
            self.addLink(switches[u], switches[v])
        
        host_id = 1
        for switch in switches.values():
            for _ in range(num_hosts // len(switches)):
                host = self.addHost(f'h{host_id}')
                self.addLink(switch, host)
                host_id += 1
        
        while host_id <= num_hosts:
            switch = switches[next(iter(switches))]
            host = self.addHost(f'h{host_id}')
            self.addLink(switch, host)
            host_id += 1

def generate_random_graph(num_switches=20):
    # Erdos-Renyi model
    graph = nx.erdos_renyi_graph(num_switches, 0.2)
    while not nx.is_connected(graph):
        graph = nx.erdos_renyi_graph(num_switches, 0.2)
    return graph

def run():
    setLogLevel('info')
    
    graph = generate_random_graph()
    
    topo = RandomGraphTopo(graph, num_hosts=50)
    net = Mininet(topo=topo, controller=RemoteController, autoSetMacs=True)
    
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)

    for switch in net.switches:
        switch.start([net.controllers[0]])
        print(f"Switch {switch.name} started")

    for host in net.hosts:
        host.cmd('ifconfig')
        print(f"Host {host.name} configured")

    CLI(net)
    net.stop()

if __name__ == '__main__':
    run()
