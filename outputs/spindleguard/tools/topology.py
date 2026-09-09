#!/usr/bin/env python3
"""Read-only, fail-closed physical-device observation. Does not route live I/O."""
import json
from pathlib import Path
import plistlib
import subprocess
import sys

class UnknownTopology(ValueError): pass

def disk_info(device):
    result=subprocess.run(['/usr/sbin/diskutil','info','-plist',device],capture_output=True,check=True)
    return plistlib.loads(result.stdout)

def physical_disks(device,info=disk_info,seen=None):
    seen=set() if seen is None else set(seen)
    if device in seen: raise UnknownTopology('Cyclic topology: '+device)
    seen.add(device)
    d=info(device)
    if d.get('RAIDMaster') or d.get('RAIDSlice') or 'RAIDSetUUID' in d:
        raise UnknownTopology('RAID mapping requires explicit support')
    stores=d.get('APFSPhysicalStores')
    if stores:
        result=set()
        for store in stores:
            child=store.get('APFSPhysicalStore')
            if not child: raise UnknownTopology('Missing APFS physical store identifier')
            result |= physical_disks(child,info,seen)
        return result
    if d.get('WholeDisk'):
        if d.get('VirtualOrPhysical')!='Physical' and not d.get('_PhysicalListConfirmed'):
            raise UnknownTopology('Whole device is not verified physical: '+device)
        return {d['DeviceIdentifier']}
    parent=d.get('ParentWholeDisk')
    if parent: return physical_disks(parent,info,seen)
    raise UnknownTopology('No physical mapping for '+device)

def resolve(path):
    path=Path(path).resolve(strict=True)
    # df obtains the mount's device without walking the source tree.
    lines=subprocess.check_output(['/bin/df','-P',str(path)],text=True).splitlines()
    device=lines[-1].split()[0]
    if not device.startswith('/dev/disk'): raise UnknownTopology('Not a local disk device')
    physical=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','list','-plist','physical']))
    confirmed={d['DeviceIdentifier'] for d in physical['AllDisksAndPartitions']}
    def verified_info(name):
        d=disk_info(name)
        d['_PhysicalListConfirmed']=d.get('DeviceIdentifier') in confirmed
        return d
    disks=sorted(physical_disks(device.removeprefix('/dev/'),verified_info))
    return {'source':str(path),'volume_device':device,'physical_disks':disks,
            'classification':{d:('ssd' if disk_info(d).get('SolidState') is True else 'unknown_or_hdd') for d in disks},
            'scope':'observational; single-root prototype queue is not a global spindle broker'}

if __name__=='__main__':
    try: print(json.dumps(resolve(sys.argv[1]),indent=2))
    except (IndexError,ValueError,OSError,subprocess.SubprocessError) as e:
        print('Topology unavailable: '+str(e),file=sys.stderr);sys.exit(2)
