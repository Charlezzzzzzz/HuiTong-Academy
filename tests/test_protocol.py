import sys, pathlib, unittest
sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))
from app.protocol import Protocol
from app.storage import MemoryStore
class TestProtocol(unittest.TestCase):
 def test_room_events(self):
  p=Protocol(store=MemoryStore()); room=p.create_room('demo'); p.add_event(room['id'],'note',{'x':1}); events=p.room_events(room['id']); self.assertEqual(events[-1]['payload'],{'x':1}); self.assertEqual(events[-1]['seq'],2)
 def test_unknown_room(self):
  with self.assertRaises(KeyError): Protocol().add_event('nope','x')
 def test_room_modes_and_idempotency(self):
  p=Protocol(store=MemoryStore()); room=p.create_room('demo', mode='production', task_id='hetong'); self.assertEqual(room['mode'],'production'); person=p.join_room(room['id'], 2, '我'); self.assertEqual(person['seat_id'],2); first=p.add_event(room['id'],'human.reply',{'text':'保留限定'}, idempotency_key='same'); second=p.add_event(room['id'],'human.reply',{'text':'重复提交'}, idempotency_key='same'); self.assertEqual(first['id'],second['id']); self.assertEqual(p.room_state(room['id'])['last_seq'],3)
 def test_store_rejects_invalid_inputs(self):
  p=Protocol(store=MemoryStore())
  with self.assertRaises(ValueError): p.create_room('demo', mode='unknown')
  room=p.create_room('demo')
  with self.assertRaises(ValueError): p.join_room(room['id'], True, '我')
  with self.assertRaises(ValueError): p.add_event(room['id'], 'bad type', {})
  with self.assertRaises(ValueError): p.add_event(room['id'], 'note', [], visibility='room')
