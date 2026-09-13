"""Finite helper checks only; no strategy or batch experiment is run."""
import copy
import unittest

from discovery_compact import COMPACT_POINTS,COMPACT_STATIONS,build_coverage_certifier
from discovery_joint_prune import choose_joint_replacement,cost_plan,MAX_NEW_ANCHORS,MAX_DELETION_TRIALS


class DiscoveryJointPruneTests(unittest.TestCase):
    def test_two_future_anchors_jointly_replace_their_pending_stops(self):
        anchors=[COMPACT_POINTS[12],COMPACT_POINTS[16]]
        actual=[point for point in COMPACT_STATIONS if point not in anchors]
        pending=anchors[:]
        tasks=[(29,[anchors[0]]),(30,[anchors[1]])]
        before=copy.deepcopy((actual,pending,tasks))
        # Duplicated obligations are the same actual points, so their deletion
        # saves no cost. The proof may pass, but a false gain is never accepted.
        result=choose_joint_replacement(actual,pending,tasks,(0.,0.),[1,2])
        self.assertEqual((actual,pending,tasks),before)
        self.assertFalse(result['accepted'])
        self.assertEqual(result['remaining'],pending)
        self.assertEqual(result['mandatory_scan_stops'],[])
        self.assertEqual(result['diagnostics']['actual_completion'],'not_assessed')
        checker=build_coverage_certifier()
        self.assertFalse(checker.certified_complete(actual))
        self.assertTrue(checker.certified_complete(actual+anchors))

    def test_real_joint_proof_can_commit_savings_and_still_requires_both_anchors(self):
        anchors=[COMPACT_POINTS[12],COMPACT_POINTS[16]]
        actual=[point for point in COMPACT_STATIONS if point not in anchors]
        pending=anchors+[(500.,0.),(-500.,0.)]
        result=choose_joint_replacement(actual,pending,[(29,[anchors[0]]),(30,[anchors[1]])],
                                        (0.,0.),[1,2])
        self.assertTrue(result['accepted'])
        self.assertEqual(set(result['mandatory_scan_stops']),set(anchors))
        self.assertGreater(result['diagnostics']['cost_saving_s'],0)
        checker=build_coverage_certifier()
        self.assertFalse(checker.certified_complete(actual))
        self.assertFalse(checker.certified_complete(actual+[anchors[0]]))
        self.assertFalse(checker.certified_complete(actual+[anchors[1]]))
        self.assertTrue(checker.certified_complete(actual+result['mandatory_scan_stops']+result['remaining']))

    def test_real_full_coverage_can_remove_redundant_pending_with_no_new_anchor(self):
        actual=list(COMPACT_STATIONS)
        pending=[(0.,0.),(400.,0.),(0.,400.),(-400.,0.),(0.,-400.),(700.,0.),(0.,700.)]
        result=choose_joint_replacement(actual,pending,[],(0.,0.),[1,2])
        self.assertTrue(result['accepted'])
        self.assertEqual(len(result['removed']),MAX_DELETION_TRIALS)
        self.assertEqual(len(result['diagnostics']['attempts']),MAX_DELETION_TRIALS)
        self.assertGreater(result['diagnostics']['cost_saving_s'],0)
        self.assertEqual(result['diagnostics']['actual_completion'],'not_assessed')

    def test_counted_scan_cost_can_reject_geometric_deletion(self):
        class PermissiveChecker:
            last_diagnostics={'coverage_uses_sampling':False}
            def certified_complete(self,points,**kwargs):return True
        tasks=[(20+i,[(100.*i,100.)]) for i in range(4)]
        result=choose_joint_replacement([],[(0.,0.)],tasks,(0.,0.),list(range(1,20)),checker=PermissiveChecker())
        self.assertFalse(result['accepted'])
        self.assertEqual(result['new_anchors'],[])
        self.assertEqual(result['remaining'],[(0.,0.)])
        self.assertTrue(result['diagnostics']['attempts'][0]['continuous_proof'])
        self.assertLess(result['diagnostics']['attempts'][0]['cost_saving_s'],0)

    def test_joint_anchors_survive_clear_success_and_failure_task_changes(self):
        class PermissiveChecker:
            last_diagnostics={'coverage_uses_sampling':False}
            def certified_complete(self,points,**kwargs):return True
        tasks=[(20,[(100.,0.),(120.,0.)]),(21,[(200.,0.)])]
        result=choose_joint_replacement([],[(900.,900.),(-900.,900.),(-900.,-900.),(900.,-900.)],
                                        tasks,(0.,0.),[1,2],checker=PermissiveChecker())
        self.assertTrue(result['accepted'])
        obligations=result['mandatory_scan_stops'][:]
        self.assertEqual(len(obligations),2)
        self.assertTrue(result['diagnostics']['clear_outcome_cannot_cancel_scan_obligation'])
        # Whether a task succeeded and disappeared or failed and moved its next
        # clear point, old mandatory locations remain separate obligations.
        for changed_tasks in ([],[(20,[(120.,0.)])]):
            next_result=choose_joint_replacement([],[],changed_tasks,(120.,0.),[1,2],
                                                 mandatory_scan_stops=obligations,checker=PermissiveChecker())
            self.assertEqual(next_result['mandatory_scan_stops'],obligations)
            self.assertEqual(next_result['diagnostics']['actual_completion'],'not_assessed')

    def test_finite_anchor_and_certificate_attempt_limits(self):
        class RecordingChecker:
            last_diagnostics={}
            def __init__(self):self.calls=[]
            def certified_complete(self,points,**kwargs):self.calls.append(points);return True
        checker=RecordingChecker()
        result=choose_joint_replacement([],[(1000.+i*100,2000.) for i in range(12)],
                                        [(i,[(i*100.,0.)]) for i in range(1,10)],(0.,0.),[1],checker=checker)
        self.assertLessEqual(len(result['diagnostics']['proposed_new_anchors']),MAX_NEW_ANCHORS)
        self.assertLessEqual(len(result['diagnostics']['attempts']),MAX_DELETION_TRIALS)
        self.assertLessEqual(len(checker.calls),1+MAX_DELETION_TRIALS)
        existing=[(-100.,0.),(-200.,0.),(-300.,0.)]
        with_obligations=choose_joint_replacement([],[(1000.,2000.)],
                        [(i,[(i*100.,0.)]) for i in range(1,10)],(0.,0.),[1],
                        mandatory_scan_stops=existing,checker=RecordingChecker())
        self.assertLessEqual(len(with_obligations['diagnostics']['proposed_new_anchors']),1)
        self.assertLessEqual(len(with_obligations['mandatory_scan_stops']),MAX_NEW_ANCHORS)

    def test_proof_failure_or_error_keeps_original_obligations(self):
        class BrokenChecker:
            last_diagnostics={}
            def certified_complete(self,points,**kwargs):raise ArithmeticError('unproved')
        actual=[(0.,0.)];pending=[(100.,0.)];existing=[(300.,0.)]
        result=choose_joint_replacement(actual,pending,[(20,[(200.,0.)])],(0.,0.),[1],
                                        mandatory_scan_stops=existing,checker=BrokenChecker())
        self.assertFalse(result['accepted'])
        self.assertEqual(result['remaining'],pending)
        self.assertEqual(result['mandatory_scan_stops'],existing)
        self.assertEqual(actual,[(0.,0.)])

    def test_costs_include_all_measure_switch_and_clear_outcomes(self):
        result=cost_plan([(0.,0.)],[(20,[(0.,0.),(10.,0.),(20.,0.)])],(0.,0.),[1,2,3],1)
        cost=result['cost']
        self.assertEqual(cost['measure_time_s'],15)
        self.assertEqual(cost['switch_time_s'],2)
        self.assertEqual(cost['clear_failure_time_s'],6)
        self.assertEqual(cost['clear_success_time_s'],5)
        self.assertEqual(cost['move_time_s'],4)
        self.assertEqual(cost['total_s'],32)
        self.assertEqual(result['terminal_receiver_channel'],3)

    def test_nearby_mandatory_stops_are_not_silently_merged(self):
        stops=[(0.,0.),(1e-8,0.)]
        result=choose_joint_replacement([],[],[],(0.,0.),[1],mandatory_scan_stops=stops)
        self.assertEqual(result['mandatory_scan_stops'],stops)
        plan=cost_plan(stops,[],(0.,0.),[1])
        self.assertEqual(plan['cost']['measure_time_s'],10)


if __name__=='__main__':
    unittest.main()
