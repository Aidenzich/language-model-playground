r"""Top ``P`` inference method."""

import argparse
from typing import ClassVar, Dict, Optional

import torch

from lmp.infer._base import BaseInfer
from lmp.model import BaseModel
from lmp.tknzr import BaseTknzr


class TopPInfer(BaseInfer):
    r"""Top ``P`` inference method.

    Use indice with the top ``P'`` highest probability as possible next token
    id, then randomly choose ``1`` index out of ``P'`` as next token id
    prediction.
    Top-p sampling, also called nucleus sampling is similar to top-k sampling
    where k changes at every step tp cover ``P`` probability mass.
    It is a non-greedy algorithm since the best prediction is not always
    choosen, but it provide dynamic of generation result (because of
    randomness, obviously).

    For comment throughout this class and its subclasses, we use ``P'`` to
    denote the number of candidate token ids with highest probabilities that
    cover ``P`` probability mass.

    Attributes
    ==========
    infer_name: ClassVar[str]
        Inference method name is ``top-p``.
        Used for command line argument parsing.
    """
    infer_name: ClassVar[str] = 'top-p'
    def __init__(self, p: float, max_seq_len: int, **kwargs: Optional[Dict]):
        super().__init__(max_seq_len=max_seq_len)
        if not isinstance(p, float):
            raise TypeError('`p` must be an instance of `float`.')
        if not p <= 1.0:
            raise ValueError('`p` must satisfy `p < 0`.')

        self.p = p

    @torch.no_grad()
    def gen(
            self,
            model: BaseModel,
            tknzr: BaseTknzr,
            txt: str,
    ) -> str:
        r"""Generate text conditional on text segment.

        Top ``P`` inference algorithm is structured as follow:

        #. Encode input text as ``1`` sample batch.
           (shape: ``(1, S')``)
        #. Remove ``[eos]`` token since model is not trained to predict tokens
           after seeing ``[eos]``.
           (shape: ``(1, S'-1)`` or ``(1, S)`` where ``S'-1 = S``)
        #. Truncate text to satisfy maximum sequence constraint.
           (shape: ``(1, S)`` or ``(1, max_seq_len)``)
        #. Use for-loop to generate sequence of token ids.

            #. Use ``model.pred()`` to get next token ids probability
               distribution.
               (shape: ``(1, S, V)``)
            #. Get the last next token id probability distribution.
               (shape: ``(1, V)``)
            #. Sort the probability distribution in descending order.
               (shape: ``(1, V)``)
            #. Get the P' highest probability distribution and their
               respective indices where P' changes at every time step to
               cover P probability mass.
               (shape: ``(1, P')``)
            #. Use top ``P'`` highest probability to construct multinomial
               distribution.
            #. Sample ``1`` index from top ``P'`` indices tensor using
               previously constructed multinomial distribution.
               Use sampled index as next token id prediction result.
               (shape: ``(1, 1)``)
            #. Concate the last next token id prediction result with previous
               next token id prediction result.
               (shape: ``(1, S+1)``)
            #. Break loop if token ids sequence length violate
               ``self.max_seq_len`` constraint.
            #. Break loop if the last next token id prediction is ``[eos]``.
            #. Otherwise go to the for-loop start and continue generation.

        #. Decode generated sequence of token ids to text and return.

        Parameters
        ==========
        model: lmp.model.BaseModel
            Pre-trained language model to generate text.
        tknzr: lmp.tknzr.BaseTknzr
            Pre-trained tokenizer for text segment encoding.
        txt: str
            Text segment to condition on.

        Returns
        =======
        str
            Generated text.
        """
        # Encode as 1 sample batch.
        batch_prev_tkids = tknzr.batch_enc(batch_txt=[txt], max_seq_len=-1)

        # Convert to tensor with `dtype == torch.int64`.
        # Tensor shape: `(1, S')`.
        # Tensor dtype: `torch.int64`.
        batch_prev_tkids = torch.LongTensor(batch_prev_tkids)

        # Remove `[eos]` token id since model is not trained to predict tokens
        # after seeing `[eos]`.
        # Tensor shape: `(1, S'-1)` or `(1, S)`.
        # Tensor dtype: `torch.int64`.
        batch_prev_tkids = batch_prev_tkids[..., :-1]

        # Satisty maximum sequence length constraint.
        # If sequence length is longer than constraint, then truncate tensor
        # to have shape `(1, self.max_seq_len)`.
        # Otherwise tensor shape remain the same.
        batch_prev_tkids = batch_prev_tkids[..., :self.max_seq_len]

        # Get model running device.
        device = next(model.parameters()).device

        # Move tensors to model running device.
        batch_prev_tkids = batch_prev_tkids.to(device)

        # Calculate how many token can be generate at most.
        # `out_seq_len` satisfy `0 <= out_seq_len <= self.max_seq_len`.
        out_seq_len = self.max_seq_len - batch_prev_tkids.size(1)

        # Generate tokens.
        for _ in range(out_seq_len):
            # Get probability distribution with current token ids.
            # Input tensor : Current token ids.
            # Input shape  : `(1, S)`.
            # Input dtype  : `torch.int64`.
            # Output tensor: Next token ids probability distribution.
            # Output shape : `(1, S, V)`.
            # Output dtype : `torch.float32`.
            batch_next_tkids_probs = model.pred(
                batch_prev_tkids=batch_prev_tkids
            )

            # Get the last token id probability distribution.
            # Only need the last token since we already know every previous
            # token ids.
            # Input tensor : Next token ids probability distribution.
            # Input shape  : `(1, S, V)`.
            # Input dtype  : `torch.float32`.
            # Output tensor: The last next token id probability distribution.
            # Output shape : `(1, V)`.
            # Output dtype : `torch.float32`.
            batch_next_tkid_probs = batch_next_tkids_probs[:, -1]

            # Sort the probability distribution in descending order.
            # `batch_topp_tkid_probs` shape  : `(1, V)`.
            # `batch_topp_tkid_probs` dtype  : `torch.float32`.
            # `batch_topp_tkid` tensor       : The top K next token id.
            # `batch_topp_tkid` shape        : `(1, V)`.
            # `batch_topp_tkid` dtype        : `torch.int64`.
            (
                batch_topp_tkid_probs,
                batch_topp_tkid,
            ) = batch_next_tkid_probs.sort(
                dim=-1,
                descending=True
            )

            # Use the token set that cover P probability mass as possible next
            # token prediction result.
            # Input tensor                   : The last next token id
            #                                  probability distribution.
            # Input shape                    : `(1, V)`.
            # Input dtype                    : `torch.float32`.
            # `batch_topp_tkid_probs` tensor : The next token id probability
            #                                  distribution which covers P
            #                                  probability mass.
            # `batch_topp_tkid_probs` shape  : `(1, P')`.
            # `batch_topp_tkid_probs` dtype  : `torch.float32`.
            # `batch_topp_tkid` tensor       : The top K next token id.
            # `batch_topp_tkid` shape        : `(1, P')`.
            # `batch_topp_tkid` dtype        : `torch.int64`.
            topp_length = 1 if batch_topp_tkid_probs[0,0] >=self.p else\
            (batch_topp_tkid_probs.cumsum(dim=-1)[0] < self.p).sum().item()

            # Only retain adequate number of probability distribution and corresponding index
            batch_topp_tkid_probs = batch_topp_tkid_probs[..., :topp_length]
            batch_topp_tkid = batch_topp_tkid[..., :topp_length]


            # Use the top K highest probabilities to construct multinomial
            # distribution, then sample index from multinomial distribution as
            # the last next token id prediction result.
            # Input tensor          : The top K next token id probability
            #                         distribution.
            # Input shape           : `(1, K)`.
            # Input dtype           : `torch.float32`.
            # Candidate index tensor: Sampled index of the top K next token id.
            #                         Sampled index is not a token id but is
            #                         an index of top K next token id tensor.
            # Candidate index shape : `(1, 1)`.
            # Candidate index dtype : `torch.int64`.
            # Next token id tensor  : Sampled token id from top K.
            #                         Use sampled index to get sampled token
            #                         id from top K next token id tensor.
            # Next token id shape   : `(1, 1)`.
            # Next token id dtype   : `torch.int64`.
            batch_next_tkid_cand_idx = torch.multinomial(
                batch_topp_tkid_probs,
                num_samples=1,
            )
            batch_next_tkid = torch.gather(
                batch_topp_tkid,
                -1,
                batch_next_tkid_cand_idx,
            )

            # Concate the last next token id prediction result with previous
            # token ids prediction result and use to perform further
            # prediction.
            # `batch_prev_tkids` shape: `(1, S)`.
            # `batch_prev_tkids` dtype: `torch.int64`.
            # `batch_next_tkid`  shape: `(1, 1)`.
            # `batch_next_tkid`  dtype: `torch.int64`.
            # Output shape            : `(1, S+1)`.
            # Output dtype            : `torch.int64`.
            batch_prev_tkids = torch.cat(
                [batch_prev_tkids, batch_next_tkid],
                dim=-1
            )

            # If the prediction token id is `[eos]`, then stop prediction.
            if batch_next_tkid[0, 0].item() == tknzr.eos_tkid:
                break

        # Output generated text.
        return tknzr.batch_dec(
            batch_tkids=batch_prev_tkids.tolist(),
            rm_sp_tks=True,
        )[0]

    @staticmethod
    def infer_parser(parser: argparse.ArgumentParser) -> None:
        r"""Top ``P`` inference method CLI arguments parser.

        Parameters
        ==========
        parser: argparse.ArgumentParser
            Parser for CLI arguments.

        See Also
        ========
        lmp.script.generate_text
            Generate text using pre-trained language model.

        Examples
        ========
        >>> import argparse
        >>> from lmp.infer import TopKInfer
        >>> parser = argparse.ArgumentParser()
        >>> TopKInfer.infer_parser(parser)
        >>> args = parser.parse_args([
        ...     '--ckpt', '5000',
        ...     '--exp_name', 'my_exp',
        ...     '--p', '.9',
        ...     '--txt', 'Hello world',
        ... ])
        >>> args.ckpt == 5000
        True
        >>> args.exp_name == 'my_exp'
        True
        >>> args.p == .9
        True
        >>> args.txt == 'Hello world'
        True
        >>> args.seed == 42
        True
        """
        # Load common arguments.
        BaseInfer.infer_parser(parser=parser)

        # Required arguments.
        group = parser.add_argument_group('inference method arguments')
        group.add_argument(
            '--p',
            help='Sample from token ids with p probabilities mass.',
            required=True,
            type=float,
        )
