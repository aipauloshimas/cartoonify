import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import doctor


class PlanTests(unittest.TestCase):
    def test_plan_order_and_only(self):
        plan = doctor.build_plan({"model", "ffmpeg", "python-packages"})
        self.assertEqual([p[0] for p in plan], ["ffmpeg", "python-packages", "model"])
        self.assertEqual([p[0] for p in doctor.build_plan({"model", "ffmpeg"}, {"model"})], ["model"])

    def test_commands(self):
        cmd = dict((n, c) for n, _, c in doctor.build_plan({"ffmpeg", "model"}))
        self.assertEqual(cmd["ffmpeg"][0], "winget" if doctor.WIN else "brew")
        self.assertEqual(cmd["model"][0], "download")


if __name__ == "__main__":
    unittest.main()
