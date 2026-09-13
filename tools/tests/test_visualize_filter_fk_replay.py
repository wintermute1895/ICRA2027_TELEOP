import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from tools.visualize_filter_fk_replay import JOINTS, SIGN, TIP, UrdfFK, estimate_fixed, pose_tf, tf

URDF=Path('assets/robots/linker_platform/sensorized/a7_dual_arm_l10_hands_cameras.urdf')

def test_urdf_chain_and_joint_order():
    fk=UrdfFK(URDF); assert fk.tip==TIP
    assert [x[0] for x in fk.chain if x[1] in ('revolute','continuous')]==JOINTS

def test_j6_sign_conversion():
    q=np.arange(1.,8.); np.testing.assert_array_equal(q*SIGN,[1,2,3,4,5,-6,7])

def test_known_zero_fk():
    T=UrdfFK(URDF)(np.zeros(7)); np.testing.assert_allclose(T[:3,3],[-0.0005,-0.171,0.713],atol=1e-9)

def test_fixed_transform_estimation():
    A=[tf([i*.01,0,0],[0,0,i*.02]) for i in range(10)]
    X=tf([.2,-.1,.3],[.1,-.2,.3]); B=[X@a for a in A]
    np.testing.assert_allclose(estimate_fixed(A,B),X,atol=1e-8)

def test_timestamp_alignment_key():
    rows=[{'episode_id':'e','header_stamp_ns':1},{'episode_id':'e','header_stamp_ns':2}]
    keys=[(x['episode_id'],x['header_stamp_ns']) for x in rows]
    assert len(keys)==len(set(keys))
