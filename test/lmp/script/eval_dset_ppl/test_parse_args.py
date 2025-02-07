"""Test parsing arguments.

Test target:
- :py:meth:`lmp.script.eval_dset_ppl.parse_args`.
"""

import lmp.script.eval_dset_ppl
from lmp.dset import DSET_OPTS


def test_parse_results(batch_size: int, exp_name: str, seed: int) -> None:
  """Must correctly parse all arguments."""
  for dset_name, dset_type in DSET_OPTS.items():
    for ver in dset_type.vers:
      for first_ckpt in [-1, 0, 1]:
        for last_ckpt in [-1, 0, 1]:
          args = lmp.script.eval_dset_ppl.parse_args(
            argv=[
              dset_name,
              '--batch_size',
              str(batch_size),
              '--exp_name',
              exp_name,
              '--first_ckpt',
              str(first_ckpt),
              '--last_ckpt',
              str(last_ckpt),
              '--seed',
              str(seed),
              '--ver',
              ver,
            ]
          )
          assert args.batch_size == batch_size
          assert args.dset_name == dset_name
          assert args.exp_name == exp_name
          assert args.first_ckpt == first_ckpt
          assert args.last_ckpt == last_ckpt
          assert args.seed == seed
          assert args.ver == ver
