import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('topology',Path(__file__).resolve().parents[1]/'tools/topology.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)

class TopologyTest(unittest.TestCase):
    def setUp(self):
        self.d={'volA':{'APFSPhysicalStores':[{'APFSPhysicalStore':'sliceA'}]},
                'volB':{'APFSPhysicalStores':[{'APFSPhysicalStore':'sliceA'}]},
                'sliceA':{'ParentWholeDisk':'diskA'},
                'diskA':{'DeviceIdentifier':'diskA','WholeDisk':True,'VirtualOrPhysical':'Physical'},
                'diskB':{'DeviceIdentifier':'diskB','WholeDisk':True,'VirtualOrPhysical':'Physical'}}
    def test_alias_volumes_share_spindle(self):
        self.assertEqual(t.physical_disks('volA',self.d.__getitem__),t.physical_disks('volB',self.d.__getitem__))
    def test_multiple_stores(self):
        self.d['volA']['APFSPhysicalStores'].append({'APFSPhysicalStore':'diskB'})
        self.assertEqual(t.physical_disks('volA',self.d.__getitem__),{'diskA','diskB'})
    def test_virtual_rejected(self):
        self.d['diskA']['VirtualOrPhysical']='Virtual'
        with self.assertRaises(t.UnknownTopology): t.physical_disks('volA',self.d.__getitem__)
    def test_cycle_rejected(self):
        self.d['sliceA']['ParentWholeDisk']='volA'
        with self.assertRaises(t.UnknownTopology): t.physical_disks('volA',self.d.__getitem__)
    def test_raid_rejected(self):
        self.d['diskA']['RAIDMaster']=True
        with self.assertRaises(t.UnknownTopology): t.physical_disks('volA',self.d.__getitem__)

if __name__=='__main__': unittest.main()
