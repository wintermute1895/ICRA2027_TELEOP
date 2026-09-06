from setuptools import setup

package_name = "hand_adapter"
setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/hand_adapter"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", ["launch/hand_interface.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="LinkerRobot",
    maintainer_email="support@linkerrobot.com",
    description="Safety-gated unified interface for O6 and L20 Lite LinkerHands.",
    license="Apache-2.0",
    entry_points={"console_scripts": ["hand_adapter = hand_adapter.hand_adapter:main"]},
)
