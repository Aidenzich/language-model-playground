"""Test parsing arguments.

Test target:
- :py:meth:`lmp.script.eval_txt_ppl.parse_args`.
"""

import lmp.script.eval_txt_ppl


def test_parse_results(exp_name: str, seed: int) -> None:
  """Must correctly parse all arguments."""
  txt = 'Hello world'
  for ckpt in [-1, 0, 1]:
    args = lmp.script.eval_txt_ppl.parse_args(
      argv=[
        '--exp_name',
        exp_name,
        '--ckpt',
        str(ckpt),
        '--seed',
        str(seed),
        '--txt',
        txt,
      ]
    )
    assert args.ckpt == ckpt
    assert args.exp_name == exp_name
    assert args.seed == seed
    assert args.txt == txt
