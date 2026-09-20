"""Strict K1 v1 radio -> existing PanoGoz Envelope adapter.

This is a codec, not a radio driver or MQTT publisher. Pass the returned Envelope
to a durable K2 outbox; acknowledge the node only after durable storage. Never
pass it through Gateway.publish(), which allocates a different sequence stream.
"""
from __future__ import annotations
import argparse, binascii, json, struct
from panogoz.contracts.assets import DEVICES_BY_KEY
from panogoz.contracts.envelope import Envelope

NODE_DEVICES={0x100+i:f'TC-{i:02}' for i in range(1,7)}
PERIODS=(900,60,10)
DATA_VALID=1
INVALID_MEASUREMENT=(1<<1)|(1<<9)

def decode(raw: bytes, *, site: str, panel: str, received_at: float | None=None) -> Envelope:
    if len(raw)!=35: raise ValueError('radio v1 frame must be exactly 35 bytes')
    if raw[0]!=0x50 or raw[1]>>4!=1: raise ValueError('unsupported magic/version')
    if int.from_bytes(raw[33:35],'little')!=binascii.crc_hqx(raw[:33],0xffff):
        raise ValueError('CRC mismatch')
    typ=raw[1]&15
    if typ not in (0,1,2,3): raise ValueError('not a TC telemetry frame')
    node=int.from_bytes(raw[2:4],'little')
    if node not in NODE_DEVICES: raise ValueError('unknown/unprovisioned node ID')
    dev=NODE_DEVICES[node];asset=DEVICES_BY_KEY[dev]
    flags=int.from_bytes(raw[13:15],'little');cad=raw[15]>>6
    if cad>=len(PERIODS):raise ValueError('invalid cadence')
    ts=int.from_bytes(raw[9:13],'little')
    unsynced=bool(flags&(1<<7))
    if unsynced:
        if received_at is None:raise ValueError('unsynced clock requires gateway reception timestamp')
        ts=received_at
    if not site or not panel or '/' in site or '/' in panel:raise ValueError('invalid site/panel')
    temp=struct.unpack_from('<h',raw,16)[0];current=int.from_bytes(raw[26:29],'little')
    values={'dev.battery_v':int.from_bytes(raw[29:31],'little')/1000,
            'dev.rssi_dbm':struct.unpack_from('<b',raw,31)[0],
            'dev.temp_mcu_c':struct.unpack_from('<b',raw,32)[0],
            'dev.period_s':PERIODS[cad], 'dev.seq':int.from_bytes(raw[4:8],'little')}
    joints={}
    if typ in (0,1) and flags&DATA_VALID and not flags&INVALID_MEASUREMENT:
        readings={}
        if temp!=-32768:readings['tc.temp_c']=temp/128
        if current!=0xffffff:readings['tc.current_a']=current/1000
        if readings:joints={asset.covers[0]:readings}
    # Raw flags belong in event metadata, not invented registry channels.
    metadata={'radio_flags':flags,'trigger_bits':raw[15]&63,'source':'k1-radio-v1',
              'clock_source':'gateway_receive' if unsynced else 'node_epoch'}
    kind={0:'data',1:'event',2:'birth',3:'state'}[typ]
    metrics=['tc.temp_c','tc.current_a',*values] if typ==2 else []
    return Envelope(kind=kind,site=site,panel=panel,device=dev,ts=ts,
                    seq=int.from_bytes(raw[4:8],'little'),boot=raw[8],
                    values=values,joints=joints,event=metadata,metrics=metrics,fw='tc-b1')

def main():
    p=argparse.ArgumentParser();p.add_argument('hex');p.add_argument('--site',required=True);p.add_argument('--panel',required=True)
    p.add_argument('--received-at',type=float);a=p.parse_args()
    e=decode(bytes.fromhex(a.hex),site=a.site,panel=a.panel,received_at=a.received_at)
    print(json.dumps({'topic':e.topic,'payload':json.loads(e.to_json())},indent=2,ensure_ascii=False))
if __name__=='__main__':main()
