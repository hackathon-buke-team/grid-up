"""Contract compatibility and corrupted/invalid sensor negative controls."""
import binascii,json
from pathlib import Path
import pytest
from firmware.tools.radio_bridge import decode
from panogoz.contracts.assets import DEVICES_BY_KEY
from panogoz.contracts.channels import CHANNELS
from panogoz.contracts.envelope import Envelope

FIXTURES=Path(__file__).parents[1]/'node/tests/radio_vectors.json'

def frame(i=0):return bytes.fromhex(json.loads(FIXTURES.read_text())[i])
def changed(raw,offset,value):
    b=bytearray(raw);b[offset]=value;b[33:]=binascii.crc_hqx(b[:33],0xffff).to_bytes(2,'little');return bytes(b)

@pytest.mark.parametrize('i',range(6))
def test_real_c_wire_roundtrip(i):
    e=decode(frame(i),site='AYDIN',panel='SOKE-14')
    assert e.device==f'TC-{i+1:02}'
    assert e.joints=={DEVICES_BY_KEY[e.device].covers[0]:{'tc.temp_c':45,'tc.current_a':120.5}}
    assert e.seq==42 and e.boot==3 and e.values['dev.period_s']==60
    assert set(e.values)<={c.name for c in CHANNELS}
    assert Envelope.from_json(e.to_json())==e
    assert e.topic==f'panogoz/v1/AYDIN/SOKE-14/data/{e.device}'

def test_corrupt_crc_rejected():
    b=bytearray(frame());b[16]^=1
    with pytest.raises(ValueError,match='CRC'):decode(bytes(b),site='A',panel='B')

@pytest.mark.parametrize('raw',[b'',b'P'*34,b'P'*36])
def test_exact_length(raw):
    with pytest.raises(ValueError,match='35'):decode(raw,site='A',panel='B')

def test_sensor_fault_never_publishes_healthy_temperature():
    e=decode(changed(frame(),14,2),site='A',panel='B')
    assert not e.joints and e.event['radio_flags']&512

def test_unsynced_clock_is_explicit():
    raw=changed(frame(),13,129)
    with pytest.raises(ValueError,match='timestamp'):decode(raw,site='A',panel='B')
    e=decode(raw,site='A',panel='B',received_at=1234)
    assert e.ts==1234 and e.event['clock_source']=='gateway_receive'

@pytest.mark.parametrize('offset,value',[(1,0x17),(3,2),(15,0xc0)])
def test_valid_crc_invalid_semantics(offset,value):
    with pytest.raises(ValueError):decode(changed(frame(),offset,value),site='A',panel='B')
