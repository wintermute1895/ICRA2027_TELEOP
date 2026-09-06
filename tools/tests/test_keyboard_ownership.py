import unittest

from tools.capture_episode import classify_input
from tools.hand_preset_controller import classify_hand_key, next_preset


class KeyboardOwnershipTest(unittest.TestCase):
    def test_f_is_hand_only_and_digits_are_annotation_only(self):
        stream = "f1f24\n"
        recorder_actions = [classify_input(char.encode()) for char in stream]
        hand_actions = [classify_hand_key(char) for char in stream]
        self.assertEqual(recorder_actions, ["ignore", "annotation", "ignore", "annotation", "annotation", "stop"])
        self.assertEqual(hand_actions, ["preset", "ignore", "preset", "ignore", "ignore", "ignore"])

    def test_hand_preset_advances_once_per_f(self):
        index = -1
        selected = []
        for key in "fffx":
            if classify_hand_key(key) == "preset":
                index, name = next_preset(["gesture_0", "gesture_1", "gesture_2", "gesture_3"], index)
                selected.append(name)
        self.assertEqual(selected, ["gesture_0", "gesture_1", "gesture_2"])


if __name__ == "__main__":
    unittest.main()
