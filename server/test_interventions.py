"""Regression cases for missed confusion alerts and independent review failures."""
import json
import unittest
import interventions as iv


class InterventionTests(unittest.TestCase):
    def review(self, **overrides):
        data = dict(needed=False, urgency='none', reason='', evidence=[])
        data.update(overrides)
        return json.dumps(data), {'input_tokens': 40, 'output_tokens': 10}

    def test_original_missed_case_overrides_ai_no(self):
        past = [{'question': 'Joj nič ne znam...', 'answer': 'Izračunaj razmerje uporov.'}]
        result, usage = iv.assess('ne razumem sploh kaj govoriš..', past,
                                  'Napetost izračunamo po formuli.', 'test', lambda p: self.review())
        self.assertTrue(result['needed'])
        self.assertEqual(result['urgency'], 'normal')
        self.assertEqual(result['rule'], 'repeated_confusion')
        self.assertEqual(result['reviewer_status'], 'evaluated')
        self.assertFalse(result['reviewer_needed'])
        self.assertEqual(result['evidence'], [past[0]['question'], 'ne razumem sploh kaj govoriš..'])
        self.assertEqual(usage['input_tokens'], 40)

    def test_explicit_request_on_failure(self):
        def broken(payload):
            raise RuntimeError('secret key should not be persisted')
        for question in ['Prosim, pokliči učitelja.', 'Potrebujem pomoč učitelja.',
                         'Lahko pokličeš učiteljico?', 'Ali lahko učitelj mi pomaga?',
                         'Rabim profesorja.', 'Rad bi pomoč učitelja.', 'Lahko mi učitelj pomaga?' ]:
            with self.subTest(question=question):
                result, usage = iv.assess(question, [], 'Počakaj.', 'test', broken)
                self.assertTrue(result['needed'])
                self.assertEqual(result['reviewer_status'], 'unavailable')
                self.assertNotIn('secret', json.dumps(result))
                self.assertEqual(usage, {})

    def test_rule_no_false_positive_examples_negation_or_resolution(self):
        past = [{'question': 'Nič ne razumem.', 'answer': 'Poišči upor.'}]
        questions = ['Zdaj razumem, hvala.', 'Ne potrebujem učitelja.', 'Ne kliči učitelja.',
                     'Učitelj je rekel, da naj preizkusim.', 'Primer: ne razumem ničesar.',
                     '»Ne razumem« je napisal sošolec.', 'Ne razumem je samo primer izjave.',
                     "'Ne razumem' je citat.", 'Ni res, da ne razumem.',
                     'Ne razumem prejšnje razlage, ampak zdaj razumem.',
                     'Ne razumem prejšnje razlage, zdaj je rešeno.']
        for question in questions:
            with self.subTest(question=question):
                self.assertFalse(iv.fallback(question, past)['needed'])
        self.assertFalse(iv.fallback('Nič ne razumem.', [])['needed'])
        self.assertFalse(iv.fallback('Nič ne razumem.', [{'question': 'Zdaj razumem.', 'answer': 'Dobro.'}] + past)['needed'])

    def test_reviewer_gets_tutor_and_bounded_context(self):
        captured = []
        def reviewer(payload):
            captured.append(payload)
            return self.review()
        past = [{'question': 'Q' * 20000, 'answer': 'A' * 20000}] * 12
        iv.assess('C' * 20000, past, 'T' * 20000, 'my-model', reviewer)
        payload = captured[0]
        data = json.loads(payload['input'][0]['content'])
        self.assertEqual(payload['model'], 'my-model')
        self.assertEqual(data['current_tutor'], 'T' * 6000)
        self.assertEqual(len(data['history']), 6)
        self.assertLess(len(payload['input'][0]['content']), 43000)
        self.assertTrue(payload['text']['format']['strict'])

    def test_reviewer_can_escalate_with_actual_evidence(self):
        question = 'Potrebujem učitelja. Na pravem vezju se kadi.'
        result, _ = iv.assess(question, [], 'Ustavi delo.', 'test', lambda p: self.review(
            needed=True, urgency='urgent', reason='Preverite resnično vezje.',
            evidence=['Na pravem vezju se kadi.']))
        self.assertTrue(result['needed'])
        self.assertEqual(result['urgency'], 'urgent')
        self.assertEqual(result['source'], 'reviewer')

    def test_reject_fabricated_tutor_or_stale_quotes(self):
        past = [{'question': 'Ne razumem.', 'answer': 'Ne razumem uporov.'}]
        for quote in ['Izmišljeno.', 'Ne razumem uporov.', 'Ne razumem.']:
            result, _ = iv.assess('Zdaj razumem.', past, 'Dobro.', 'test', lambda p: self.review(
                needed=True, urgency='normal', reason='Pomagajte.', evidence=[quote]))
            self.assertEqual(result['status'], 'unavailable')
            self.assertFalse(result['needed'])

    def test_unavailable_distinct_from_evaluated_no(self):
        for raw in ['bad json', '{}', '{"needed": false}', '[]']:
            result, _ = iv.assess('Kateri upor?', [], 'Ta.', 'test', lambda p: (raw, {}))
            self.assertEqual(result['status'], 'unavailable')
        result, _ = iv.assess('Kateri upor?', [], 'Ta.', 'test', lambda p: self.review())
        self.assertEqual(result['status'], 'evaluated')
        self.assertFalse(result['needed'])

    def test_legacy_decode_kept(self):
        text = json.dumps({'answer': 'Pozdrav.', 'teacher_alert': json.loads(self.review()[0])})
        answer, result = iv.decode(text, 'Živijo.', [])
        self.assertEqual(answer, 'Pozdrav.')
        self.assertEqual(result['status'], 'evaluated')


if __name__ == '__main__':
    unittest.main()
