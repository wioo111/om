"""只验证新增协作层的比较口径与场景生成，不重跑算法审计。"""
import unittest
from collab.bench import make_suite, paired_summary, validate_suite


def record(case, seconds, n=10, cleared=10, error=None):
    return dict(case_id=case, N=n, cleared=cleared, clear_rate=cleared/n,
                virtual_time_s=seconds * cleared,
                avg_time_per_cleared=seconds if cleared else None,
                measure_count=1, error=error)


class CollaborationTests(unittest.TestCase):
    def test_screen_balanced_and_validation_contains_stress(self):
        screen = make_suite('screen')
        validate_suite(screen)
        self.assertEqual(len(screen['cases']), 21)
        self.assertEqual({n: sum(r['N'] == n for r in screen['cases']) for n in range(10,17)},
                         {n: 3 for n in range(10,17)})
        final = make_suite('validation', 54321)
        validate_suite(final)
        self.assertEqual(sum(r['group']=='main' for r in final['cases']), 70)
        self.assertEqual(sum(r['group']=='stress' for r in final['cases']), 24)
        self.assertTrue({r['seed'] for r in screen['cases']}.isdisjoint(r['seed'] for r in final['cases']))

    def test_pairing_rejects_different_cases(self):
        with self.assertRaises(ValueError):
            paired_summary([record('one', 250)], [record('two', 200)])

    def test_failure_cannot_be_rewarded_as_faster(self):
        result = paired_summary([record('one', 250)], [record('one', 1, cleared=1)])
        self.assertFalse(result['all_full_clear'])
        self.assertIsNone(result['mean_delta_s'])
        self.assertFalse(result['screening_pass'])
        false_counter = record('one', 1)
        false_counter['clear_rate'] = 0.0
        result = paired_summary([record('one', 250)], [false_counter])
        self.assertFalse(result['all_full_clear'])

    def test_paired_reduction_and_small_sample_is_not_promotion(self):
        result = paired_summary([record('a',250),record('b',300)],
                                [record('a',200),record('b',250)])
        self.assertEqual(result['mean_delta_s'], -50)
        self.assertEqual(result['paired_ci95_normal'], [-50,-50])
        self.assertFalse(result['screening_pass'])


if __name__ == '__main__':
    unittest.main()
