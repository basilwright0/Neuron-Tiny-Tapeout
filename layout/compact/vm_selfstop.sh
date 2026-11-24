#!/bin/bash
# Runs ON the boat VM: when the done marker appears, wait GRACE seconds (default 300, time to copy results back),
# then stop the VM itself (`boat stop` snapshots the disk; resume to fetch anything left).
# Usage: vm_selfstop.sh <VM id> <done marker> [GRACE]. Note: `boat extend self --ttl` does NOT stop a VM.
ID=$1; MARK=$2; GRACE=${3:-300}
until [ -f "$MARK" ]; do sleep 30; done
sleep "$GRACE"
BOAT_ID=$ID /home/user/.ascii/boat stop self > /home/user/selfstop.log 2>&1
