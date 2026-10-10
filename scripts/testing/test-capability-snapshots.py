#!/usr/bin/env python3
"""Snapshot rotation/failure preservation and read-only health regression tests."""
from datetime import datetime, timedelta, timezone
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts/ai/lib'))
import capability_snapshots as snapshots


def report(hour=0):
    return {'schema': 'capability-audit/1', 'generated_at': f'2026-10-09T{hour:02d}:00:00Z',
            'repo_root': '/repo', 'live_root': '/repo', 'window_days': 30,
            'capabilities': [{'key': 'aq-example', 'class': 'BROKEN', 'evidence': {
                'discoverable': True, 'used': False, 'wired': True, 'tested': False,
                'stale': False, 'dead': False, 'discovered_in': ['repo'], 'wired_by': ['config'],
                'use_sources': [], 'discovered_in_count': 1, 'wired_by_count': 1,
                'tested_by_count': 0, 'use_count': 0, 'last_seen': None, 'broken': 'failure'}}],
            'totals': {'capabilities': 1, 'by_class': {c: int(c == 'BROKEN') for c in snapshots.CLASSES}}}


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'snapshot.json'

    def test_fresh_malformed_evidence_is_invalid(self):
        for field, value in [('evidence', None), ('discoverable', 'true'), ('use_count', -1)]:
            bad = report(1)
            row = bad['capabilities'][0]
            if field == 'evidence':
                row.pop(field)
            else:
                row['evidence'][field] = value
            self.path.write_text(json.dumps({'schema': 'capability-audit-snapshots/1',
                                            'previous': report(0), 'current': bad}))
            self.assertEqual(snapshots.snapshot_status(
                self.path, datetime(2026, 10, 9, 2, tzinfo=timezone.utc))['status'], 'invalid')
            with self.assertRaises(ValueError):
                snapshots.validate_report(bad)

    def test_three_rotations_preserve_previous_current(self):
        snapshots.write_snapshot(self.path, report(0))
        self.assertIsNone(json.loads(self.path.read_text())['previous'])
        snapshots.write_snapshot(self.path, report(1))
        snapshots.write_snapshot(self.path, report(2))
        bundle = json.loads(self.path.read_text())
        self.assertEqual(bundle['previous'], report(1))
        self.assertEqual(bundle['current'], report(2))

    def test_invalid_prior_is_preserved(self):
        self.path.write_text('{bad json')
        with self.assertRaises(ValueError):
            snapshots.write_snapshot(self.path, report(1))
        self.assertEqual(self.path.read_text(), '{bad json')

    def test_invalid_new_report_or_scope_is_preserved(self):
        snapshots.write_snapshot(self.path, report(0))
        original = self.path.read_bytes()
        bad = report(1)
        bad['totals']['by_class']['BROKEN'] = 0
        with self.assertRaises(ValueError):
            snapshots.write_snapshot(self.path, bad)
        bad = report(1)
        bad['live_root'] = '/other'
        with self.assertRaises(ValueError):
            snapshots.write_snapshot(self.path, bad)
        self.assertEqual(self.path.read_bytes(), original)

    def test_atomic_replace_failure_preserves_prior(self):
        snapshots.write_snapshot(self.path, report(0))
        original = self.path.read_bytes()
        with patch.object(snapshots.os, 'replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                snapshots.write_snapshot(self.path, report(1))
        self.assertEqual(self.path.read_bytes(), original)

    def test_cli_failed_audit_preserves_prior(self):
        loader = importlib.machinery.SourceFileLoader('audit_cli_snapshot_test', str(REPO / 'scripts/ai/aq-capability-audit'))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        cli = importlib.util.module_from_spec(spec)
        loader.exec_module(cli)
        target = Path(self.tmp.name) / snapshots.SNAPSHOT_PATH
        snapshots.write_snapshot(target, report(0))
        original = target.read_bytes()
        with patch.object(sys, 'argv', ['aq-capability-audit', '--snapshot', '--live-root', self.tmp.name]), patch.object(cli.ca, 'run_audit', side_effect=RuntimeError('probe failure')):
            with self.assertRaises(RuntimeError):
                cli.main()
        self.assertEqual(target.read_bytes(), original)

    def test_status_never_reports_missing_invalid_initial_stale_future_as_fresh(self):
        now = datetime(2026, 10, 9, 2, tzinfo=timezone.utc)
        self.assertEqual(snapshots.snapshot_status(self.path, now)['status'], 'missing')
        self.path.write_text('{}')
        self.assertEqual(snapshots.snapshot_status(self.path, now)['status'], 'invalid')
        snapshots.write_snapshot(self.path.with_name('initial.json'), report(0))
        self.assertEqual(snapshots.snapshot_status(self.path.with_name('initial.json'), now)['status'], 'warming-up')
        self.path.write_text(json.dumps({'schema': 'capability-audit-snapshots/1', 'previous': report(0), 'current': report(1)}))
        self.assertEqual(snapshots.snapshot_status(self.path, now)['status'], 'fresh')
        self.assertEqual(snapshots.snapshot_status(self.path, now + timedelta(hours=26))['status'], 'stale')
        self.assertEqual(snapshots.snapshot_status(self.path, now - timedelta(hours=2))['status'], 'invalid')


if __name__ == '__main__':
    unittest.main()
