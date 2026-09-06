#!/usr/bin/env python3
"""Launch LeRobot ACT training with non-contiguous episode support.

LeRobot 0.3.2 builds ``episode_data_index`` in selected-episode order but
looks it up with the original episode index.  This wrapper remaps that lookup
while leaving metadata and timestamp validation unchanged.
"""
from __future__ import annotations

from lerobot.datasets.lerobot_dataset import LeRobotDataset


_ORIGINAL_GET_QUERY_INDICES = LeRobotDataset._get_query_indices


def _get_query_indices_compat(self, idx: int, ep_idx: int):
    episodes = self.episodes
    if episodes is not None:
        mapping = getattr(self, "_selected_episode_position", None)
        if mapping is None:
            mapping = {
                int(original): position
                for position, original in enumerate(episodes)
            }
            self._selected_episode_position = mapping
        ep_idx = mapping[int(ep_idx)]
    return _ORIGINAL_GET_QUERY_INDICES(self, idx, ep_idx)


LeRobotDataset._get_query_indices = _get_query_indices_compat

from lerobot.scripts.train import main  # noqa: E402


if __name__ == "__main__":
    main()
