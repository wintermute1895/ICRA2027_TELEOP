from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from robot_teleop.task_config import load_task_bundle, resolve_registered_task


class TaskConfigTest(unittest.TestCase):
  def test_directory_bundle_resolves_and_is_hashed(self):
    bundle, hashes = load_task_bundle(ROOT / "config/tasks/power_button_press_v1")
    self.assertEqual(bundle["task_id"], "power_button_press_v1")
    self.assertEqual(bundle["task_revision"], "power_button_press_v1")
    self.assertTrue(bundle["capture_contract"]["manual_segments"])
    self.assertTrue(bundle["task_bundle_sha256"])
    self.assertNotIn(str(ROOT / "config/tasks/power_button_press_v1/task.yaml"), hashes)
    self.assertIn("config/tasks/power_button_press_v1/task.yaml", hashes)


  def test_legacy_flat_profile_remains_supported(self):
    bundle, _ = load_task_bundle(ROOT / "config/tasks/usb_c_insertion_v1.yaml")
    self.assertEqual(bundle["task_id"], "usb_c_insertion_v1")
    self.assertEqual(bundle["task_family"], "connector_insertion_v1")


  def test_missing_bundle_is_rejected(self):
    with self.assertRaisesRegex(ValueError, "not found"):
        load_task_bundle(ROOT / "config/tasks/does_not_exist")


  def test_registry_is_data_driven(self):
    bundle, _ = resolve_registered_task("power_button_press_v1")
    self.assertEqual(bundle["task_id"], "power_button_press_v1")


if __name__ == "__main__":
    unittest.main()
