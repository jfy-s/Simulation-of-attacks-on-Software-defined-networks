from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.util import pmonitor
from mininet.log import setLogLevel
from time import sleep, time
import random

class CustomTopology(Topo):
    def build(self, size=5):
        switches = [self.addSwitch(f's{i+1}') for i in range(size)]
        hosts = [self.addHost(f'h{i+1}') for i in range(size)]

        for i in range(size - 1):
            self.addLink(switches[i], switches[i+1])
            self.addLink(hosts[i], switches[i])

        self.addLink(hosts[-1], switches[-1])

def test_network(net, duration=300, bandwidth_range=(10, 100), min_interval=0.5, max_interval=2.0, min_duration=3, max_duration=10):
    popens = {}
    hosts = list(net.hosts)
    start_time = time()

    while time() - start_time < duration:
        h1, h2 = random.sample(hosts, 2)
        bandwidth = random.randint(*bandwidth_range)
        current_duration = random.randint(min_duration, max_duration)
        server_port = 5001 + hosts.index(h2)

        if h2 not in popens:
            server_cmd = f'iperf -s -u -p {server_port} &'
            popens[h2] = h2.popen(server_cmd, shell=True)
            print(f"{time() - start_time:.2f}s: Server started on {h2.name} (port {server_port})")

        client_cmd = f'iperf -c {h2.IP()} -u -b {bandwidth}M -t {current_duration} -p {server_port}'
        popens[h1] = h1.popen(client_cmd, shell=True)
        print(f"{time() - start_time:.2f}s: {h1.name} started sending {bandwidth}M to {h2.name} for {current_duration}s")

        interval = random.uniform(min_interval, max_interval)
        sleep(interval)

    for host, line in pmonitor(popens, timeoutms=500):
        if host and line:
            print(f"{time() - start_time:.2f}s: {host.name} output: {line.strip()}")

    for p in popens.values():
        p.terminate()
    print(f"Test completed after {time() - start_time:.2f}s")

def run():
    topo = CustomTopology(size=3)
    net = Mininet(topo=topo, controller=RemoteController('c0', ip='127.0.0.1'), switch=OVSKernelSwitch, autoSetMacs=True)
    net.start()
    sleep("3s")
    print("Starting network tests...")
    test_network(net)
    net.stop()

if __name__ == "__main__":
    setLogLevel('info')
    run()
