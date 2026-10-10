# SPDX-License-Identifier: GPL-3.0-or-later
import json
import unittest
import learning


class LearningTest(unittest.TestCase):
    def test_snapshot_diff_ignores_clock_and_measurements(self):
        old = {'components': [{'id': 'R1', 'type': 'Resistor', 'properties': {'Resistance': {'value': '1', 'unit': 'kΩ'}}, 'pins': [{'voltage_V': None}]}], 'connections': [{'id': 'W1', 'from': 'R1-a', 'to': 'V-a'}]}
        new = json.loads(json.dumps(old))
        new['components'][0]['pins'][0]['voltage_V'] = 5
        new['captured_utc'] = 'later'
        self.assertEqual(learning.snapshot_diff(old, new)['changes'], [])
        new['components'][0]['properties']['Resistance']['value'] = '2'
        new['connections'][0]['to'] = 'Ground-a'
        changes = learning.snapshot_diff(old, new)['changes']
        self.assertEqual({c['field'] for c in changes}, {'properties', 'to'})
        self.assertEqual(learning.snapshot_diff(None, new)['status'], 'baseline')

    def test_challenge_sequence_hints_profile(self):
        state = learning.challenge_start({'components': []})
        public = learning.challenge_public(state)
        self.assertNotIn('3,75', public['prompt'])
        self.assertNotIn('baseline_snapshot', public)
        with self.assertRaises(ValueError): learning.challenge_submit(state, {'step': 2, 'answer': '1'})
        state = learning.challenge_hint(state)
        state = learning.challenge_submit(state, {'step': 0, 'answer': 'Naraste'})
        self.assertEqual(state['points'], 10)
        self.assertEqual(len(state['answers']), 1)
        with self.assertRaises(ValueError): learning.challenge_submit(state, {'step': 1, 'answer': 'nan; pojasnilo ...'})
        state = learning.challenge_submit(state, {'step': 1, 'answer': '3,75 V; spodnji upor ima večji delež skupne upornosti.'})
        self.assertTrue(state['answers'][-1]['numeric_matches'])
        self.assertIsNone(state['answers'][-1]['correct'])
        state = learning.challenge_submit(state, {'step': 2, 'answer': '1 kΩ'})
        self.assertTrue(learning.challenge_public(state)['completed'])
        self.assertEqual(state['points'], 30)
        with self.assertRaises(ValueError): learning.challenge_submit(state, {'step': 2, 'answer': '1'})
        profile = learning.concept_profile([{'id': 5, 'lesson_id': 2, 'state': json.dumps(state)}])
        self.assertEqual(profile[0]['status'], 'pravilen odgovor z namigom')
        self.assertEqual(profile[1]['status'], 'razlaga čaka pregled')
        self.assertEqual(profile[2]['evidence'][0]['attempt_id'], 5)

    def test_points_do_not_claim_mastery(self):
        state = learning.challenge_submit(learning.challenge_start(), {'step': 0, 'answer': 'Pade'})
        self.assertEqual(state['points'], 10)
        self.assertEqual(learning.concept_profile([state])[0]['status'], 'potrebuje nadaljnje preverjanje')

    def test_summary_fairness_and_repeated_attempts(self):
        rows = [{'id': n, 'user_id': 1, 'question': 'x'*3501, 'answer': 'y'*3501} for n in range(20)]
        rows.append({'id': 21, 'user_id': 2, 'question': 'Potrebujem pomoč', 'answer': 'Preveriva.'})
        result = learning.lesson_summary(rows)
        self.assertIn(21, result['coverage']['exchange_ids'])
        self.assertEqual(result['coverage']['included_students'], 2)
        self.assertTrue(result['coverage']['text_truncated'])
        state = learning.challenge_submit(learning.challenge_start(), {'step': 0, 'answer': 'Naraste'})
        profile = learning.concept_profile([state, state])
        self.assertIn('ponovitvi', profile[0]['status'])

    def test_summary_validates_evidence_and_limits_context(self):
        rows = [{'id': n, 'user_id': 1, 'question': 'x'*3500, 'answer': 'y'*3500} for n in range(30)]
        def model(payload):
            self.assertLess(len(json.dumps(payload)), 70000)
            return json.dumps({'overview': 'Pregled', 'findings': [{'text': 'Nerazumevanje.', 'exchange_ids': [9999]}]}), {}
        summary = learning.lesson_summary(rows, call_model=model)
        self.assertEqual(summary['status'], 'fallback')
        self.assertTrue(summary['coverage']['partial'])
        valid = learning.lesson_summary(rows[:1], call_model=lambda p: (json.dumps({'overview': 'Pregled', 'findings': [{'text': 'Študent sprašuje.', 'exchange_ids': [0]}]}), {}))
        self.assertEqual(valid['status'], 'generated')
        local = learning.lesson_summary([{'id': 1, 'user_id': 3, 'assessment': {'needed': True, 'reason': 'Pomoč.'}}])
        self.assertEqual(local['findings'][0]['exchange_ids'], [1])


if __name__ == '__main__': unittest.main()
