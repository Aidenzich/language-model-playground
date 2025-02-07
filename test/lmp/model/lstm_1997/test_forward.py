"""Test forward pass of :py:class:`lmp.model.LSTM1997`.

Test target:
- :py:meth:`lmp.model.LSTM1997.forward`.
"""

import torch

from lmp.model import LSTM1997


def test_forward_path(
  lstm_1997: LSTM1997,
  batch_cur_tkids: torch.Tensor,
  batch_next_tkids: torch.Tensor,
) -> None:
  """Parameters used during forward pass must have gradients."""
  # Make sure model has zero gradients at the begining.
  lstm_1997 = lstm_1997.train()
  lstm_1997.zero_grad()

  loss = lstm_1997(batch_cur_tkids=batch_cur_tkids, batch_next_tkids=batch_next_tkids)
  loss.backward()

  assert loss.size() == torch.Size([])
  assert loss.dtype == torch.float
  assert hasattr(lstm_1997.emb.weight, 'grad')
  assert hasattr(lstm_1997.h_0, 'grad')
  assert hasattr(lstm_1997.c_0, 'grad')
  assert hasattr(lstm_1997.proj_e2c.weight, 'grad')
  assert hasattr(lstm_1997.proj_e2c.bias, 'grad')
  assert hasattr(lstm_1997.proj_h2c.weight, 'grad')
  assert hasattr(lstm_1997.proj_h2e.weight, 'grad')
  assert hasattr(lstm_1997.proj_h2e.bias, 'grad')
