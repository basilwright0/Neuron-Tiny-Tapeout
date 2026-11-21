#!/bin/bash
# Runs ON the boat VM: when the done marker appears, shorten the VM's own lifetime to GRACE seconds (default 600) so it
# auto-stops (snapshot kept) even if no local watcher is alive. Usage: vm_selfstop.sh <VM id> <done marker> [GRACE]
ID=$1; MARK=$2; GRACE=${3:-600}
until [ -f "$MARK" ]; do sleep 30; done
BOAT_ID=$ID /home/user/.ascii/boat extend self --ttl "$GRACE" > /home/user/selfstop.log 2>&1
