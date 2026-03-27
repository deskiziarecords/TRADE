#!/bin/bash
# /opt/rpd/scripts/setup-network.sh
# Run as root on colo server

# 1. Kernel boot parameters
GRUB_CMDLINE="default_hugepagesz=1G hugepagesz=1G hugepages=8 \
    intel_iommu=on iommu=pt \
    isolcpus=2-15 nohz_full=2-15 rcu_nocbs=2-15 \
    skew_tick=1"

# 2. NIC tuning
IFACE="eth0"
ethtool -L $IFACE combined 8  # 8 queues
ethtool -G $IFACE rx 4096 tx 4096
ethtool -K $IFACE tso off gso off gro off lro off
ethtool -K $IFACE rxvlan off txvlan off
ethtool -C $IFACE rx-usecs 0 tx-usecs 0
ethtool -N $IFACE rx-flow-hash tcp4 0  # Disable RSS hash (deterministic)

# 3. IRQ affinity
for irq in $(cat /proc/interrupts | grep $IFACE | awk '{print $1}' | tr -d ':'); do
    echo $(printf '%x' $((1 << (irq % 8 + 2)))) > /proc/irq/$irq/smp_affinity
done

# 4. io_uring limits
echo 1000000 > /proc/sys/fs/nr_open
ulimit -n 1000000

# 5. Kernel TLS (if using)
modprobe tls

echo "[$(date -Iseconds)] Network stack tuned" >> /var/log/rpd-net.log
