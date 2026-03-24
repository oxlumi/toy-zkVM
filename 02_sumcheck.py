import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Exercise 2: The Sumcheck Protocol

    **Goal**: Run sumcheck by hand on a concrete constraint polynomial. See how
    "check a sum over all rows" reduces to "check one evaluation at a random point."

    We'll upgrade our toy CPU to **4 cycles** (n=2 variables) so sumcheck has
    2 rounds and the halving pattern is visible.

    ---

    ## Setup: A 4-cycle program over F_97

    The program: `result = ((a * b) + c) * d`

    | Cycle | Op  | Left | Right | Out |
    |-------|-----|------|-------|-----|
    | 0     | MUL | 3    | 5     | 15  |
    | 1     | ADD | 15   | 7     | 22  |
    | 2     | MUL | 22   | 4     | 88  |
    | 3     | ADD | 88   | 0     | 88  |

    Cycle 3 is padding (add 0) to reach a power of 2.
    """)
    return


@app.cell
def _():
    P = 97

    def add(a, b):
        return (a + b) % P

    def sub(a, b):
        return (a - b) % P

    def mul(a, b):
        return (a * b) % P

    def inv(a):
        return pow(a, P - 2, P)

    return P, add, mul, sub


@app.cell
def _():
    trace = {
        "left":  [3, 15, 22, 88],
        "right": [5,  7,  4,  0],
        "out":   [15, 22, 88, 88],
        "op":    [0,  1,  0,  1],   # 0=MUL, 1=ADD
    }
    return (trace,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 1: MLEs with 2 variables

    With T=4 cycles, we need n=2 variables (since 2^2 = 4). Each cycle gets a 2-bit address:

    | Cycle | Address (x1, x2) |
    |-------|-------------------|
    | 0     | (0, 0)            |
    | 1     | (0, 1)            |
    | 2     | (1, 0)            |
    | 3     | (1, 1)            |

    The MLE formula for 2 variables uses the eq polynomial as selector:

    $$\widetilde{f}(x_1, x_2) = \sum_{b \in \{0,1\}^2} f(b) \cdot \widetilde{eq}((x_1,x_2), b)$$

    where $\widetilde{eq}((x_1,x_2),(b_1,b_2)) = [(1-x_1)(1-b_1) + x_1 b_1] \cdot [(1-x_2)(1-b_2) + x_2 b_2]$
    """)
    return


@app.cell
def _(P, add, mul, sub):
    def eq_factor(x, b):
        """One factor of eq~: matches variable x to bit b."""
        if b == 0:
            return sub(1, x)  # (1 - x)
        else:
            return x  # x

    def make_mle_2var(values):
        """
        Build MLE for a 4-element vector (2 variables).
        values[0] = f(0,0), values[1] = f(0,1), values[2] = f(1,0), values[3] = f(1,1)
        """
        _v = [v % P for v in values]

        def mle(x1, x2):
            _total = 0
            for _b1 in range(2):
                for _b2 in range(2):
                    _idx = _b1 * 2 + _b2
                    _eq = mul(eq_factor(x1, _b1), eq_factor(x2, _b2))
                    _total = add(_total, mul(_v[_idx], _eq))
            return _total

        return mle

    return (make_mle_2var,)


@app.cell
def _(make_mle_2var, trace):
    # Build MLEs for all columns
    left_poly = make_mle_2var(trace["left"])
    right_poly = make_mle_2var(trace["right"])
    out_poly = make_mle_2var(trace["out"])
    op_poly = make_mle_2var(trace["op"])

    # Verify: evaluate on all boolean points
    _addresses = [(0, 0), (0, 1), (1, 0), (1, 1)]
    print("Verifying MLEs on the boolean hypercube:")
    for _name, _poly, _col in [
        ("left", left_poly, trace["left"]),
        ("right", right_poly, trace["right"]),
        ("out", out_poly, trace["out"]),
        ("op", op_poly, trace["op"]),
    ]:
        for _i, (_b1, _b2) in enumerate(_addresses):
            _v = _poly(_b1, _b2)
            _e = _col[_i]
            _ok = "✓" if _v == _e else "✗"
            print(f"  {_name}~({_b1},{_b2}) = {_v}  (expected {_e}) {_ok}")
    return left_poly, op_poly, out_poly, right_poly


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 2: The constraint polynomial (2 variables)

    Same rule as before, but now `C(x1, x2)` is a polynomial in two variables:

    $$C(x_1, x_2) = \text{out}(x_1,x_2) - [(1-\text{op}) \cdot \text{left} \cdot \text{right} + \text{op} \cdot (\text{left} + \text{right})]$$

    It should be 0 at all four boolean points (all four cycles are valid).
    """)
    return


@app.cell
def _(add, left_poly, mul, op_poly, out_poly, right_poly, sub):
    def C(x1, x2):
        """Constraint polynomial: returns 0 if the cycle is valid."""
        _l = left_poly(x1, x2)
        _r = right_poly(x1, x2)
        _o = out_poly(x1, x2)
        _op = op_poly(x1, x2)
        _mul_res = mul(_l, _r)
        _add_res = add(_l, _r)
        _expected = add(mul(sub(1, _op), _mul_res), mul(_op, _add_res))
        return sub(_o, _expected)

    print("Constraint check on all 4 cycles:")
    for _b1 in range(2):
        for _b2 in range(2):
            _v = C(_b1, _b2)
            _cycle = _b1 * 2 + _b2
            print(f"  C({_b1},{_b2}) [cycle {_cycle}] = {_v}  {'✓' if _v == 0 else '✗'}")
    return (C,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 3: The claim

    The verifier wants to check:

    $$H = \sum_{(x_1, x_2) \in \{0,1\}^2} C(x_1, x_2) = 0$$

    They could evaluate C at all 4 points and add them up. But in a real system
    with T=65536 cycles that means touching all $2^{16}$ rows, which defeats the purpose.

    **Sumcheck lets the verifier check this sum using only 2 rounds (= n variables)
    and one final evaluation of C.**

    Let's compute the actual sum first to confirm it's 0:
    """)
    return


@app.cell
def _(C, add):
    # Compute the sum directly (the verifier can't do this in practice, but we check)
    H = 0
    print("Computing H = Σ C(x1,x2) over {0,1}²:")
    for _b1 in range(2):
        for _b2 in range(2):
            _v = C(_b1, _b2)
            print(f"  C({_b1},{_b2}) = {_v}")
            H = add(H, _v)
    print(f"\n  H = {H}  {'✓ sum is 0!' if H == 0 else '✗ sum is not 0'}")
    return (H,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 4: Sumcheck Round 1

    The prover needs to convince the verifier that $H = 0$ without the verifier
    evaluating C at all 4 points.

    **Round 1**: The prover "peels off" variable $x_1$. They compute a univariate polynomial:

    $$s_1(X) = \sum_{x_2 \in \{0,1\}} C(X, x_2)$$

    This sums over the remaining variable ($x_2$), leaving a polynomial in $X$ alone.

    The verifier checks: $s_1(0) + s_1(1) = H = 0$

    Why does this work? When you plug in $X=0$ and $X=1$ and add:
    - $s_1(0) = C(0,0) + C(0,1)$
    - $s_1(1) = C(1,0) + C(1,1)$
    - $s_1(0) + s_1(1) = C(0,0) + C(0,1) + C(1,0) + C(1,1) = H$ ✓

    Let's compute $s_1$ as a table of values:
    """)
    return


@app.cell
def _(C, H, add):
    # PROVER computes s_1(X) = C(X, 0) + C(X, 1)
    # We'll evaluate at X = 0, 1, 2, 3 to get enough points to identify the polynomial.
    # (Our constraint poly has degree 3 in x1 because of the left*right product, so s_1 has degree ≤ 3 and we need 4 points.)

    def s1(X):
        """Round 1 polynomial: sum over x2 of C(X, x2)"""
        return add(C(X, 0), C(X, 1))

    # Prover sends s1 to verifier (as evaluations at a few points)
    print("Prover computes s1(X) = C(X,0) + C(X,1):")
    print(f"  s1(0) = C(0,0) + C(0,1) = {C(0,0)} + {C(0,1)} = {s1(0)}")
    print(f"  s1(1) = C(1,0) + C(1,1) = {C(1,0)} + {C(1,1)} = {s1(1)}")

    # VERIFIER checks: s1(0) + s1(1) should equal H
    _check = add(s1(0), s1(1))
    print(f"\nVerifier checks: s1(0) + s1(1) = {s1(0)} + {s1(1)} = {_check}")
    print(f"  Expected H = {H}")
    print(f"  {'✓ Match!' if _check == H else '✗ MISMATCH!'}")

    # Verifier picks a random challenge r1
    # (In a real system this comes from Fiat-Shamir. Here we just pick one.)
    r1 = 23  # "random" challenge
    _new_claim = s1(r1)
    print(f"\nVerifier samples random r1 = {r1}")
    print(f"  New claim: s1({r1}) = {_new_claim}")
    print(f"  This means: Σ_{{x2}} C({r1}, x2) should equal {_new_claim}")
    return r1, s1


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 5: Sumcheck Round 2

    After round 1, the claim has been reduced from:
    - "the sum over both variables is 0"

    to:
    - "the sum over x2 alone, with x1 fixed to r1, equals s1(r1)"

    **Round 2**: The prover computes:

    $$s_2(X) = C(r_1, X)$$

    No more summing, there's only one variable left! The verifier checks: $s_2(0) + s_2(1) = s_1(r_1)$
    """)
    return


@app.cell
def _(C, add, r1, s1):
    # PROVER computes s2(X) = C(r1, X), now just the constraint at a fixed x1
    def s2(X):
        """Round 2 polynomial: C(r1, X) with r1 already bound."""
        return C(r1, X)

    _claim_from_round1 = s1(r1)
    print(f"Prover computes s2(X) = C({r1}, X):")
    print(f"  s2(0) = C({r1}, 0) = {s2(0)}")
    print(f"  s2(1) = C({r1}, 1) = {s2(1)}")

    # VERIFIER checks: s2(0) + s2(1) = s1(r1)
    _check2 = add(s2(0), s2(1))
    print(f"\nVerifier checks: s2(0) + s2(1) = {s2(0)} + {s2(1)} = {_check2}")
    print(f"  Expected (from round 1): s1({r1}) = {_claim_from_round1}")
    print(f"  {'✓ Match!' if _check2 == _claim_from_round1 else '✗ MISMATCH!'}")

    # Verifier picks final random challenge r2
    r2 = 71  # "random"
    _final_claim = s2(r2)
    print(f"\nVerifier samples random r2 = {r2}")
    print(f"  Final claim: C({r1}, {r2}) should equal {_final_claim}")
    return r2, s2


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 6: The Final Check

    After n=2 rounds, sumcheck has reduced the claim to a **single evaluation**:

    $$C(r_1, r_2) = \text{final\_claim}$$

    The verifier now evaluates $C(r_1, r_2)$ directly (or gets this from an oracle/PCS).

    This is the moment of truth: if the prover was honest, the values match.
    If the prover cheated, Schwartz-Zippel says they get caught with high probability.
    """)
    return


@app.cell
def _(C, r1, r2, s2):
    # VERIFIER evaluates C(r1, r2) directly
    _final_claim = s2(r2)
    _actual = C(r1, r2)

    print(f"Final verification:")
    print(f"  Claimed: C({r1}, {r2}) = {_final_claim}")
    print(f"  Actual:  C({r1}, {r2}) = {_actual}")
    print(f"  {'✓ SUMCHECK PASSES!' if _final_claim == _actual else '✗ SUMCHECK FAILS!'}")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## What just happened?

    Tracing the full protocol:

    ```
    Claim: H = Σ C(x1,x2) = 0
                    │
    Round 1:  Prover sends s1(X) = Σ_{x2} C(X, x2)
              Verifier checks: s1(0) + s1(1) = H     ✓
              Verifier samples r1 = 23
              New claim: Σ_{x2} C(23, x2) = s1(23)
                    │
    Round 2:  Prover sends s2(X) = C(23, X)
              Verifier checks: s2(0) + s2(1) = s1(23) ✓
              Verifier samples r2 = 71
              New claim: C(23, 71) = s2(71)
                    │
    Final:    Verifier evaluates C(23, 71) directly    ✓
    ```

    **The verifier never looked at all 4 rows of the trace!**

    They checked:
    1. One consistency check per round (s(0) + s(1) = previous claim)
    2. One final evaluation C(r1, r2)

    That's it. For a real Jolt trace with 65536 rows and 16 variables, the verifier does
    16 consistency checks + 1 final evaluation, instead of touching all 65536 rows.

    ---

    ## The verifier's work vs the prover's work

    | | Prover | Verifier |
    |---|--------|----------|
    | Round 1 | Sum C(X, 0)+C(X,1) for many X values | Check s1(0)+s1(1)=H, pick r1 |
    | Round 2 | Evaluate C(r1, X) for a few X values | Check s2(0)+s2(1)=s1(r1), pick r2 |
    | Final | — | Evaluate C(r1, r2) |
    | **Total** | **O(2^n) work** | **O(n) checks + 1 evaluation** |

    The prover does the heavy lifting. The verifier is cheap. This asymmetry is
    the whole point of sumcheck (and SNARKs in general).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---

    ## Why does this catch cheaters?

    Suppose the prover has a **bad trace** (some constraint is violated, so the real sum H' != 0)
    but they claim H = 0.

    - **Round 1**: They must send some fake $\hat{s}_1$ with $\hat{s}_1(0) + \hat{s}_1(1) = 0$.
      But the real $s_1$ has $s_1(0) + s_1(1) = H' \neq 0$.
      So $\hat{s}_1 \neq s_1$ as polynomials.
      Two different degree-d polynomials agree on at most d points out of 97.
      The verifier picks $r_1$ randomly -> probability of $\hat{s}_1(r_1) = s_1(r_1)$ is at most $d/97$.

    - **If they get unlucky** (which is almost certain): $\hat{s}_1(r_1) \neq s_1(r_1)$,
      so the claim going into round 2 is wrong, and the error propagates.

    - **Final check**: The verifier evaluates $C(r_1, r_2)$ directly. If any round was
      dishonest, this won't match.

    In real systems over 254-bit fields, the cheating probability is $\sim d/2^{254}$ per round. Negligible.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---

    ## Exercises

    **1.** Change `r1` to a different value (say 50) and re-run. Does sumcheck still pass?

    > Yes, it should pass for any r1.

    **2.** Corrupt the trace: set `out[2] = 89` instead of 88. What happens to H? Does sumcheck catch it?

    > H becomes 1 (not 0), which means the constraint is violated. Sumcheck would catch this at the very first step: the verifier knows the sum must be 0, so when the prover sends s1 and the verifier computes s1(0) + s1(1) = 1 ≠ 0, it rejects immediately. The notebook doesn't show this because it checks against the computed H rather than the hardcoded target of 0, but in the real protocol the verifier never computes H, they just check against 0.

    **3.** In our 2-round sumcheck, how many field elements does the prover send total? *(Count: s1 needs enough points to describe a degree-d polynomial, same for s2.)*

    > The prover sends 8 field elements total (4 per round). Each round polynomial has degree 3 (because the constraint multiplies three degree-1 polynomials: (1-op) · left · right), and a degree-3 polynomial needs 4 evaluation points for the verifier to reconstruct it and evaluate at the random challenge. So it's 2 rounds × 4 elements = 8.

    **4.** In real Jolt with T=65536 cycles (n=16 variables), how many rounds does sumcheck take? How many consistency checks does the verifier do? Compare to the 65536 rows the verifier *doesn't* touch.

    >  16 rounds, 16 consistency checks, 1 final evaluation.

    **Next**: Exercise 3 will make this non-interactive using Fiat-Shamir (hash the prover's messages to get the challenges).
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
