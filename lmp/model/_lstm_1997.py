"""LSTM (1997 version) language model."""

import argparse
import math
from typing import Any, ClassVar, List, Optional, Tuple, Union

import torch
import torch.nn as nn
import torch.nn.functional as F

import lmp.util.validate
from lmp.model._base import BaseModel
from lmp.tknzr._base import BaseTknzr


class LSTM1997(BaseModel):
  r"""LSTM (1997 version) [1]_ language model.

  Implement RNN model in the paper `Long Short-Term Memory`_.

  - Let :math:`x[t]` be the :math:`t`-th token id in the input token id list :math:`x` as defined in
    :py:class:`lmp.model.BaseModel`.
  - Let ``d_emb`` be the dimension of token embeddings and let ``vocab_size`` be the vocabulary size of tokenizer.
  - Let ``n_cell`` be the number of memory cells and let ``d_cell`` be the dimension of each memory cell.

  Then LSTM (1997 version) is defined as follow:

  .. math::

     \newcommand{\pa}[1]{\left( #1 \right)}
     \newcommand{\set}[1]{\left\lbrace #1 \right\rbrace}
     \newcommand{\concate}[1]{\operatorname{concate}\pa{#1}}
     \newcommand{\ncell}{n_{\operatorname{cell}}}
     \newcommand{\hbar}{\overline{h}}
     \newcommand{\sigmoid}[1]{\operatorname{sigmoid}\pa{#1}}
     \newcommand{\softmax}[1]{\operatorname{softmax}\pa{#1}}
     \begin{align*}
       e[t]           & = (x[t])\text{-th column of } E                                          \\
       i[t + 1]       & = \sigmoid{W^i \cdot e[t] + U^i \cdot h[t] + b^i}                        \\
       o[t + 1]       & = \sigmoid{W^o \cdot e[t] + U^o \cdot h[t] + b^o}                        \\
       k              & \in \set{1, 2, \dots, \ncell}                                            \\
       g^k[t + 1]     & = 4 \cdot \sigmoid{W^k \cdot e[t] + U^k \cdot h[t] + b^k} - 2            \\
       c^k[t + 1]     & = c^k[t] + i_k[t + 1] \cdot g^k[t + 1]                                   \\
       \hbar^k[t + 1] & = o_k[t + 1] \cdot \pa{2 \cdot \sigmoid{c^k[t + 1]} - 1}                 \\
       h[t + 1]       & = \concate{\hbar^1[t + 1], \hbar^2[t + 1], \dots, \hbar^{\ncell}[t + 1]} \\
       z[t + 1]       & = \sigmoid{W^z \cdot h[t + 1] + b^z}                                     \\
       y[t + 1]       & = \softmax{E^{\top} \cdot z[t + 1]}
     \end{align*}

  +------------------------------------------------+---------------------------------------------------+
  | Trainable Parameters                           | Nodes                                             |
  +----------------+-------------------------------+------------------------+--------------------------+
  | Parameter      | Shape                         | Symbol                 | Shape                    |
  +================+===============================+========================+==========================+
  | :math:`E`      | ``(d_emb, vocab_size)``       | :math:`e[t]`           | ``(d_emb, 1)``           |
  +----------------+-------------------------------+------------------------+--------------------------+
  | :math:`h[0]`   | ``(n_cell x d_cell, 1)``      |                                                   |
  +----------------+-------------------------------+------------------------+--------------------------+
  | :math:`W^i`,   | ``(n_cell, d_emb)``           | :math:`i[t + 1]`,      | ``(n_cell, 1)``          |
  | :math:`W^o`    |                               | :math:`o[t + 1]`       |                          |
  +----------------+-------------------------------+------------------------+--------------------------+
  | :math:`U^i`,   | ``(n_cell, n_cell x d_cell)`` |                                                   |
  | :math:`U^o`    |                               |                                                   |
  +----------------+-------------------------------+                                                   |
  | :math:`b^i`,   | ``(n_cell, 1)``               |                                                   |
  | :math:`b^o`    |                               |                                                   |
  +----------------+-------------------------------+------------------------+--------------------------+
  | :math:`W^k`    | ``(d_cell, d_emb)``           | :math:`g^k[t + 1]`,    | ``(d_cell, 1)``          |
  +----------------+-------------------------------+ :math:`c^k[t + 1]`,    |                          |
  | :math:`U^k`    | ``(d_cell, n_cell x d_cell)`` | :math:`\hbar^k[t + 1]` |                          |
  +----------------+-------------------------------+------------------------+--------------------------+
  | :math:`b^k`    | ``(d_cell, 1)``               |                                                   |
  +----------------+-------------------------------+------------------------+--------------------------+
  | :math:`c^k[0]` | ``(d_cell, 1)``               | :math:`h[t + 1]`       | ``(n_cell x d_cell, 1)`` |
  +----------------+-------------------------------+------------------------+--------------------------+
  | :math:`W^z`    | ``(d_emb, n_cell x d_cell)``  | :math:`z[t + 1]`       | ``(d_emb, 1)``           |
  +----------------+-------------------------------+------------------------+--------------------------+
  | :math:`b^z`    | ``(d_emb, 1)``                | :math:`y[t + 1]`       | ``(vocab_size, 1)``      |
  +----------------+-------------------------------+------------------------+--------------------------+

  - :math:`E` is the token embedding lookup table as defined in :py:class:`lmp.model.ElmanNet`.
  - :math:`i[t + 1], o[t + 1]` are input gates and output gates at time step :math:`t + 1`, respectively.
  - :math:`g^k[t + 1]` is the :math:`k`-th memory cell's input activation at time step :math:`t + 1`.  There are
    ``n_cell`` different memory cell's activations, i.e., :math:`g^1[t + 1], \dots, g^{\ncell}[t + 1]`.
  - :math:`c^k[t + 1]` is the :math:`k`-th memory cell's internal state at time step :math:`t + 1`.  The initial
    internal state :math:`c^k[0]` is a pre-defined column vector.
  - The hidden state :math:`h[t + 1]` at time step :math:`t + 1` is based on the output of all LSTM cells at time step
    :math:`t + 1`, i.e., :math:`\hbar^1[t + 1], \dots \hbar^{\ncell}[t + 1]`.  The initial hidden state :math:`h[0]` is
    a pre-defined column vector.
  - After performing another sigmoid-activated affine transformation, the final output :math:`y[t + 1]`, i.e., the next
    token id prediction probability distribution can be calculated.  We use the same calculation as
    :py:class:`lmp.model.ElmanNet`.

  Parameters
  ----------
  d_cell: int
    Memory cell dimension.
  d_emb: int
    Token embedding dimension.
  kwargs: typing.Any, optional
    Useless parameter.  Intently left for subclasses inheritance.
  n_cell: int
    Number of memory cells.
  tknzr: lmp.tknzr.BaseTknzr
    Tokenizer instance.

  Attributes
  ----------
  c_0: torch.nn.Parameter
    Initial memory cell's internal states.
  d_cell: int
    Memory cell dimension.
  emb: torch.nn.Embedding
    Token embedding lookup table.
  h_0: torch.nn.Parameter
    Initial hidden states.
  loss_fn: torch.nn.CrossEntropyLoss
    Loss function to be optimized.
  model_name: ClassVar[str]
    CLI name of LSTM (1997 version) is ``LSTM-1997``.
  n_cell: int
    Number of memory cells.
  proj_e2c: torch.nn.Linear
    Fully connected layer which connects input units to memory cells.  Input dimension is ``d_emb``.  Output dimension
    is ``n_cell * (2 + d_cell)``.
  proj_h2c: torch.nn.Linear
    Fully connected layer which connects hidden states to memory cells.  Input dimension is ``n_cell * d_cell``.
    Output dimension is ``n_cell * (2 + d_cell)``.
  proj_h2e: torch.nn.Linear
    Fully connected layer which connects hidden states to embedding dimension.  Input dimension is ``n_cell * d_cell``.
    Output dimension is ``d_emb``.

  See Also
  --------
  lmp.model.BaseModel
    Language model utilities.
  lmp.model.ElmanNet
    LSTM (1997 version) language model.

  References
  ----------
  .. [1] S. Hochreiter and J. Schmidhuber, "`Long Short-Term Memory`_," in Neural Computation, vol. 9, no. 8,
     pp. 1735-1780, 15 Nov. 1997, doi: 10.1162/neco.1997.9.8.1735.

  .. _`Long Short-Term Memory`:
     https://ieeexplore.ieee.org/abstract/document/6795963
  """

  model_name: ClassVar[str] = 'LSTM-1997'

  def __init__(self, *, d_cell: int, d_emb: int, n_cell: int, tknzr: BaseTknzr, **kwargs: Any):
    super().__init__(**kwargs)
    # `d_cell` validation.
    lmp.util.validate.raise_if_not_instance(val=d_cell, val_name='d_cell', val_type=int)
    lmp.util.validate.raise_if_wrong_ordered(vals=[1, d_cell], val_names=['1', 'd_cell'])
    self.d_cell = d_cell

    # `d_emb` validation.
    lmp.util.validate.raise_if_not_instance(val=d_emb, val_name='d_emb', val_type=int)
    lmp.util.validate.raise_if_wrong_ordered(vals=[1, d_emb], val_names=['1', 'd_emb'])

    # `n_cell` validation.
    lmp.util.validate.raise_if_not_instance(val=n_cell, val_name='n_cell', val_type=int)
    lmp.util.validate.raise_if_wrong_ordered(vals=[1, n_cell], val_names=['1', 'n_cell'])
    self.n_cell = n_cell

    # `tknzr` validation.
    lmp.util.validate.raise_if_not_instance(val=tknzr, val_name='tknzr', val_type=BaseTknzr)

    # Token embedding layer.  Use token ids to perform token embeddings lookup.
    self.emb = nn.Embedding(num_embeddings=tknzr.vocab_size, embedding_dim=d_emb, padding_idx=tknzr.pad_tkid)

    # Fully connected layer which connects input units to memory cells.
    self.proj_e2c = nn.Linear(in_features=d_emb, out_features=n_cell * (2 + d_cell))

    # Fully connected layer which connects hidden states to memory cells.
    self.proj_h2c = nn.Linear(in_features=n_cell * d_cell, out_features=n_cell * (2 + d_cell), bias=False)

    # Initial hidden states and initial memory cell internal states.  First dimension is set to `1` to broadcast along
    # batch dimension.
    self.h_0 = nn.Parameter(torch.zeros(1, n_cell * d_cell))
    self.c_0 = nn.Parameter(torch.zeros(1, n_cell, d_cell))

    # Fully connected layer which project hidden states to embedding dimension.
    self.proj_h2e = nn.Linear(in_features=n_cell * d_cell, out_features=d_emb)

    # Calculate cross entropy loss for all non-padding tokens.
    self.loss_fn = nn.CrossEntropyLoss(ignore_index=tknzr.pad_tkid)

    # Initialize model parameters.
    self.params_init()

  def params_init(self) -> None:
    r"""Initialize model parameters.

    All weights and non-gate units's biases are initialized with uniform distribution
    :math:`\mathcal{U}\pa{\frac{-1}{\sqrt{v}}, \frac{1}{\sqrt{v}}}` where :math:`v =` ``max(d_emb, n_cell x d_cell)``.
    Gate units' biases are initialized with uniform distribution :math:`\mathcal{U}\pa{\frac{-1}{\sqrt{v}}, 0}`.

    Returns
    -------
    None
    """
    # Initialize weights and biases with uniform distribution.
    d_hid = self.n_cell * self.d_cell
    inv_sqrt_dim = 1 / math.sqrt(max(self.emb.embedding_dim, d_hid))
    nn.init.uniform_(self.emb.weight, -inv_sqrt_dim, inv_sqrt_dim)
    nn.init.uniform_(self.proj_e2c.weight, -inv_sqrt_dim, inv_sqrt_dim)
    nn.init.uniform_(self.proj_e2c.bias[:d_hid], -inv_sqrt_dim, inv_sqrt_dim)
    nn.init.uniform_(self.proj_h2c.weight, -inv_sqrt_dim, inv_sqrt_dim)
    nn.init.uniform_(self.h_0, -inv_sqrt_dim, inv_sqrt_dim)
    nn.init.uniform_(self.c_0, -inv_sqrt_dim, inv_sqrt_dim)
    nn.init.uniform_(self.proj_h2e.weight, -inv_sqrt_dim, inv_sqrt_dim)
    nn.init.uniform_(self.proj_h2e.bias, -inv_sqrt_dim, inv_sqrt_dim)

    # Gate units' biases are initialized to negative values.
    nn.init.uniform_(self.proj_e2c.bias[d_hid:d_hid + self.n_cell], -inv_sqrt_dim, 0.0)
    nn.init.uniform_(self.proj_e2c.bias[d_hid + self.n_cell:], -inv_sqrt_dim, 0.0)

  def forward(self, batch_cur_tkids: torch.Tensor, batch_next_tkids: torch.Tensor) -> torch.Tensor:
    """Calculate language model training loss.

    This method must only be used to train model.  For inference use :py:meth:`lmp.model.ElmanNet.pred` instead.
    Forward pass algorithm is structured as follow:

    #. Use token ids to lookup token embeddings with ``self.emb``.
    #. Use ``self.proj_e2c`` and ``self.proj_h2c`` to calculate memory cells and gate units.  In this step we use
       teacher forcing, i.e., inputs are directly given instead generated by model.
    #. Use ``self.proj_h2e`` to project hidden states to embedding dimension.
    #. Calculate similarity scores by calculating inner product over all token embeddings.
    #. Return cross-entropy loss.

    Parameters
    ----------
    batch_cur_tkids: torch.Tensor
      Batch of token ids which represent input token ids of all time steps.  ``batch_cur_tkids`` has shape
      ``(batch_size, seq_len)`` and ``dtype == torch.int``.
    batch_next_tkids: torch.Tensor
      Batch of token ids which represent prediction targets of all time steps.  ``batch_next_tkids`` has the same shape
      and ``dtype`` as ``batch_cur_tkids``.

    Returns
    -------
    torch.Tensor
      Cross entropy loss on next token id prediction. Returned tensor has shape ``(1)`` and ``dtype == torch.float``.
    """
    # Sequence length.
    seq_len = batch_cur_tkids.size(1)

    # Token embedding lookup and project from embedding layer to memory cells.
    # In  shape: (batch_size, seq_len).
    # Out shape: (batch_size, seq_len, n_cell x (2 + d_cell)).
    cells_and_gates_input_by_emb = self.proj_e2c(self.emb(batch_cur_tkids))

    # Perform recurrent calculation for `seq_len` steps.  We use teacher forcing, i.e., the current input `e[:, i, :]`
    # is used instead of generated by model.
    d_hid = self.n_cell * self.d_cell
    z_all = []
    c_prev: Union[torch.Tensor, nn.Parameter] = self.c_0
    h_prev: Union[torch.Tensor, nn.Parameter] = self.h_0
    for i in range(seq_len):
      # Project `h_prev` from hidden states to memory cells.  Then calculate memory cells and gates input activation.
      # shape: (batch_size, n_cell x (2 + d_cell)).
      cells_and_gates_input_act = torch.sigmoid(cells_and_gates_input_by_emb[:, i, :] + self.proj_h2c(h_prev))

      # Calculate memory cells input activation and reshape to separate memory cells.
      # shape: (batch_size, n_cell, d_cell)
      cells_input_act = 4 * cells_and_gates_input_act[:, :d_hid] - 2
      cells_input_act = cells_input_act.reshape(-1, self.n_cell, self.d_cell)

      # Get input gates.
      # shape: (batch_size, n_cell, 1)
      input_gates = cells_and_gates_input_act[:, d_hid:d_hid + self.n_cell].unsqueeze(2)

      # Calculate current memory cells' internal states.
      # shape: (batch_size, n_cell, d_cell)
      c_cur = c_prev + input_gates * cells_input_act

      # Get output gates.
      # shape: (batch_size, n_cell, 1)
      output_gates = cells_and_gates_input_act[:, d_hid + self.n_cell:].unsqueeze(2)

      # Calculate current memory cells' outputs and reshape to fit the shape of hidden state.
      # shape: (batch_size, n_cell x d_cell)
      h_cur = output_gates * (2 * torch.sigmoid(c_cur) - 1)
      h_cur = h_cur.reshape(-1, d_hid)

      # Project from hidden states to embedding dimension.
      # shape: (batch_size, d_emb)
      z_all.append(torch.sigmoid(self.proj_h2e(h_cur)))

      # Update hidden states and memory cells' internal states.
      c_prev = c_cur
      h_prev = h_cur

    # Stack list of tensors into single tensor.
    # In  shape: list of (batch_size, d_emb) with length equals to `seq_len`.
    # Out shape: (batch_size, seq_len, d_emb).
    z = torch.stack(z_all, dim=1)

    # Calculate similarity scores by calculating inner product over all token embeddings.
    # shape: (batch_size, seq_len, vocab_size).
    sim = z @ self.emb.weight.transpose(0, 1)

    # Reshape logits to calculate loss.
    # shape: (batch_size x seq_len, vocab_size).
    sim = sim.reshape(-1, self.emb.num_embeddings)

    # Reshape target to calculate loss.
    # shape: (batch_size x seq_len).
    batch_next_tkids = batch_next_tkids.reshape(-1)

    # Calculate cross-entropy loss.
    # Out shape : (1).
    return self.loss_fn(sim, batch_next_tkids)

  @torch.no_grad()
  def pred(
    self,
    batch_cur_tkids: torch.Tensor,
    batch_prev_states: Optional[List[torch.Tensor]] = None,
  ) -> Tuple[torch.Tensor, List[torch.Tensor]]:
    """Calculate next token id probability distribution given previous hidden states and current input token id.

    This method must only be used for inference.  For training use :py:meth:`lmp.model.ElmanNet.forward` instead.  No
    tensor graphs will be constructed and no gradients will be calculated.

    Parameters
    ----------
    batch_cur_tkids: torch.Tensor
      Batch of current input token ids.  ``batch_cur_tkids`` has shape ``(batch_size)`` and ``dtype == torch.int``.
    batch_prev_states: typing.Optional[list[torch.Tensor]], default: None
      Batch of previous calculation results.  Set to ``None`` to use initial hidden states and memory cells' internal
      states.  ``batch_prev_states`` must has two items, the first item will be used as hidden states and the second
      item will be used as memory cells' internal states.

    Returns
    -------
    tuple[torch.Tensor, list[torch.Tensor]]
      The first item in the tuple is the tensor of batch of next token id probability distribution with shape
      ``(batch_size, vocab_size)`` and ``dtype == torch.float``.  The second item in the tuple is a list of tensor
      which represent current hiddent states and current memory cells' internal states.
    """
    # Use initial hidden state if `batch_prev_state is None`.
    if batch_prev_states is None:
      batch_prev_states = [self.h_0, self.c_0]

    h_prev = batch_prev_states[0]
    c_prev = batch_prev_states[1]

    # Token embedding lookup and project from embedding layer to memory cells.
    # In  shape: (batch_size).
    # Out shape: (batch_size, n_cell x (2 + d_cell)).
    cells_and_gates_input_by_emb = self.proj_e2c(self.emb(batch_cur_tkids))

    # Project `h_prev` from hidden states to memory cells.  Then calculate memory cells and gates input activation.
    # shape: (batch_size, n_cell x (2 + d_cell)).
    cells_and_gates_input_act = torch.sigmoid(cells_and_gates_input_by_emb + self.proj_h2c(h_prev))

    # Calculate memory cells input activation and reshape to separate memory cells.
    # shape: (batch_size, n_cell, d_cell)
    d_hid = self.n_cell * self.d_cell
    cells_input_act = 4 * cells_and_gates_input_act[:, :d_hid] - 2
    cells_input_act = cells_input_act.reshape(-1, self.n_cell, self.d_cell)

    # Get input gates.
    # shape: (batch_size, n_cell, 1)
    input_gates = cells_and_gates_input_act[:, d_hid:d_hid + self.n_cell].unsqueeze(2)

    # Calculate current memory cells' internal states.
    # shape: (batch_size, n_cell, d_cell)
    c_cur = c_prev + input_gates * cells_input_act

    # Get output gates.
    # shape: (batch_size, n_cell, 1)
    output_gates = cells_and_gates_input_act[:, d_hid + self.n_cell:].unsqueeze(2)

    # Calculate current memory cells' outputs and reshape to fit the shape of hidden state.
    # shape: (batch_size, n_cell x d_cell)
    h_cur = output_gates * (2 * torch.sigmoid(c_cur) - 1)
    h_cur = h_cur.reshape(-1, d_hid)

    # Project from hidden states to embedding dimension.
    # shape: (batch_size, d_emb)
    z = torch.sigmoid(self.proj_h2e(h_cur))

    # Calculate similarity scores by calculating inner product over all token embeddings.
    # shape: (batch_size, vocab_size).
    sim = z @ self.emb.weight.transpose(0, 1)

    # Calculate next token id probability distribution using softmax.
    # shape: (batch_size, vocab_size).
    batch_next_tkids_pd = F.softmax(sim, dim=-1)

    return (batch_next_tkids_pd, [h_cur, c_cur])

  @classmethod
  def train_parser(cls, parser: argparse.ArgumentParser) -> None:
    """CLI arguments parser for training LSTM (1997 version) language model.

    Parameters
    ----------
    parser: argparse.ArgumentParser
      CLI arguments parser.

    Returns
    -------
    None

    See Also
    --------
    lmp.model.BaseModel.train_parser
      CLI arguments parser for training language model.
    lmp.script.train_model
      Language model training script.

    Examples
    --------
    >>> import argparse
    >>> from lmp.model import LSTM1997
    >>> parser = argparse.ArgumentParser()
    >>> LSTM1997.train_parser(parser)
    >>> args = parser.parse_args([
    ...   '--batch_size', '32',
    ...   '--beta1', '0.9',
    ...   '--beta2', '0.99',
    ...   '--ckpt_step', '1000',
    ...   '--d_cell', '64',
    ...   '--d_emb', '100',
    ...   '--dset_name', 'wiki-text-2',
    ...   '--eps', '1e-8',
    ...   '--exp_name', 'my_exp',
    ...   '--log_step', '200',
    ...   '--lr', '1e-4',
    ...   '--max_norm', '1',
    ...   '--max_seq_len', '128',
    ...   '--n_cell', '8',
    ...   '--n_epoch', '10',
    ...   '--tknzr_exp_name', 'my_tknzr_exp',
    ...   '--ver', 'train',
    ...   '--wd', '1e-2',
    ... ])
    >>> args.batch_size == 32
    True
    >>> args.beta1 == 0.9
    True
    >>> args.beta2 == 0.99
    True
    >>> args.ckpt_step == 1000
    True
    >>> args.d_cell == 64
    True
    >>> args.d_emb == 100
    True
    >>> args.dset_name == 'wiki-text-2'
    True
    >>> args.eps == 1e-8
    True
    >>> args.exp_name == 'my_exp'
    True
    >>> args.log_step == 200
    True
    >>> args.lr == 1e-4
    True
    >>> args.max_norm == 1
    True
    >>> args.max_seq_len == 128
    True
    >>> args.n_cell == 8
    True
    >>> args.n_epoch == 10
    True
    >>> args.seed == 42
    True
    >>> args.tknzr_exp_name == 'my_tknzr_exp'
    True
    >>> args.ver == 'train'
    True
    >>> args.wd == 1e-2
    True
    """
    # Load common arguments.
    super().train_parser(parser=parser)

    # Required arguments.
    group = parser.add_argument_group('LSTM (1997 version) training arguments')
    group.add_argument(
      '--d_cell',
      help='Memory cell dimension.',
      required=True,
      type=int,
    )
    group.add_argument(
      '--d_emb',
      help='Token embedding dimension.',
      required=True,
      type=int,
    )
    group.add_argument(
      '--n_cell',
      help='Number of memory cells.',
      required=True,
      type=int,
    )
