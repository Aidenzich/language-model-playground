"""Test prediction of :py:class:`lmp.model.LSTM1997`.

Test target:
- :py:meth:`lmp.model.LSTM1997.pred`.
"""

import torch

from lmp.model import LSTM1997


def test_prediction_result(lstm_1997: LSTM1997, batch_cur_tkids: torch.Tensor) -> None:
  """Return float tensor with correct shape and range."""
  lstm_1997 = lstm_1997.eval()
  seq_len = batch_cur_tkids.size(1)

  batch_prev_states = None
  for i in range(seq_len):
    batch_next_tkids_pd, batch_prev_states = lstm_1997.pred(
      batch_cur_tkids=batch_cur_tkids[..., i],
      batch_prev_states=batch_prev_states,
    )

    # Output float tensor.
    assert batch_next_tkids_pd.dtype == torch.float

    # Shape: (batch_size, vocab_size).
    assert batch_next_tkids_pd.size() == torch.Size([batch_cur_tkids.shape[0], lstm_1997.emb.num_embeddings])

    # Probabilities are values within range [0, 1].
    assert torch.all(0 <= batch_next_tkids_pd).item()
    assert torch.all(batch_next_tkids_pd <= 1).item()

    # Sum of the probabilities equals to 1.
    accum = batch_next_tkids_pd.sum(dim=-1)
    assert torch.allclose(accum, torch.ones_like(accum))

    assert isinstance(batch_prev_states, list)
    assert len(batch_prev_states) == 2
    assert batch_prev_states[0].size() == torch.Size([batch_cur_tkids.size(0), lstm_1997.n_cell * lstm_1997.d_cell])
    assert batch_prev_states[1].size() == torch.Size([batch_cur_tkids.size(0), lstm_1997.n_cell, lstm_1997.d_cell])
