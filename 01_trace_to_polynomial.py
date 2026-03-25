import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Exercise 1: From Program to Trace to Polynomial

    **Goal**: Understand how a program's execution becomes a polynomial that a proof system can reason about.

    We'll work over **F_97** (the field of integers mod 97) so every number is small and hand-checkable.

    ## The "program"

    Our toy program computes `output = a * b + c`. That's it, one multiplication, one addition.
    Think of it as a 2-cycle CPU:

    | Cycle | Operation | Inputs     | Output |
    |-------|-----------|------------|--------|
    | 0     | MUL       | a=3, b=5   | 15     |
    | 1     | ADD       | 15, c=7    | 22     |

    The program's claim: **"given inputs (3, 5, 7), the output is 22"**.

    A zkVM proves this claim without revealing the intermediate value 15.
    """)
    return


@app.cell
def _():
    # Our field: integers mod 97
    P = 97

    def add(a, b):
        return (a + b) % P

    def sub(a, b):
        return (a - b) % P

    def mul(a, b):
        return (a * b) % P

    def inv(a):
        """Modular inverse via Fermat's little theorem: a^{-1} = a^{p-2} mod p"""
        return pow(a, P - 2, P)

    def neg(a):
        return (P - a) % P

    # Quick sanity check
    assert mul(3, inv(3)) == 1
    assert add(50, 50) == 3  # 100 mod 97 = 3
    return P, add, mul, sub


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 1: The Execution Trace

    The trace is a table where each row is one "cycle" and each column is a wire.
    This is the **witness**, the private data the prover knows.

    Our tiny CPU has 4 wires per cycle:
    - `left`: left input
    - `right`: right input
    - `out`: output of the operation
    - `op`: 0 = MUL, 1 = ADD
    """)
    return


@app.cell
def _():
    # The execution trace, this IS the witness
    trace = {
        "left": [3, 15],  # left operand each cycle
        "right": [5, 7],  # right operand each cycle
        "out": [15, 22],  # result each cycle
        "op": [0, 1],  # 0=MUL, 1=ADD
    }

    # T = number of cycles
    T = len(trace["left"])
    print(f"Trace has T = {T} cycles")
    print()

    for _cycle in range(T):
        _op_name = "MUL" if trace["op"][_cycle] == 0 else "ADD"
        print(
            f"  Cycle {_cycle}: {_op_name}({trace['left'][_cycle]}, {trace['right'][_cycle]}) = {trace['out'][_cycle]}"
        )
    return (trace,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 2: From Trace Column to Polynomial (MLE)

    Each column of the trace is a vector of T=2 values. We turn it into a **multilinear polynomial**
    using the Multilinear Extension (MLE).

    Since T = 2 = 2^1, we need **n = 1 variable**. Each cycle gets a 1-bit address:
    - Cycle 0 -> address `(0)`
    - Cycle 1 -> address `(1)`

    The MLE formula for 1 variable is simply:

    $$\widetilde{f}(x) = f(0) \cdot (1 - x) + f(1) \cdot x$$

    This is just linear interpolation! Let's compute it for the `left` column: values [3, 15].
    """)
    return


@app.cell
def _(P, add, mul, sub, trace):
    # MLE of the "left" column: [3, 15]
    # f~(x) = f(0)·(1-x) + f(1)·x = 3·(1-x) + 15·x

    def left_mle(x):
        """MLE of [3, 15] over F_97"""
        _f0 = trace["left"][0]  # = 3
        _f1 = trace["left"][1]  # = 15
        _term0 = mul(_f0, sub(1, x))
        _term1 = mul(_f1, x)
        return add(_term0, _term1)

    # Verify on the boolean hypercube: should recover original values
    print("Checking left_mle on boolean points:")
    print(f"  left~(0) = {left_mle(0)}  (expected: {trace['left'][0]})")
    print(f"  left~(1) = {left_mle(1)}  (expected: {trace['left'][1]})")
    assert left_mle(0) == trace["left"][0]
    assert left_mle(1) == trace["left"][1]
    print("  ✓ Matches!")

    # But we can also evaluate at NON-boolean points!
    print(
        f"\n  left~(50) = {left_mle(50)}  <- this is the polynomial 'between' the data"
    )

    # Let's also see the explicit formula
    # f~(x) = 3·(1-x) + 15·x = 3 - 3x + 15x = 3 + 12x
    # In F_97: coefficient of x is (15 - 3) mod 97 = 12
    _slope = sub(trace["left"][1], trace["left"][0])
    _intercept = trace["left"][0]
    print(f"\n  Explicit: left~(x) = {_intercept} + {_slope}·x  (mod {P})")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 3: Build MLEs for All Columns

    Now let's generalize. We'll build a function that takes any column and returns its MLE.
    """)
    return


@app.cell
def _(P, add, mul, sub, trace):
    def make_mle_1var(values):
        """
        Build MLE for a 2-element vector (1 variable).
        Returns a function F_97 -> F_97.
        """
        _f0, _f1 = values[0] % P, values[1] % P

        def mle(x):
            return add(mul(_f0, sub(1, x)), mul(_f1, x))

        return mle

    # Build MLEs for all 4 columns
    left_poly = make_mle_1var(trace["left"])
    right_poly = make_mle_1var(trace["right"])
    out_poly = make_mle_1var(trace["out"])
    op_poly = make_mle_1var(trace["op"])

    # Verify all of them on boolean points
    print("Verifying all column MLEs on {0, 1}:")
    for _name, _poly, _col in [
        ("left", left_poly, trace["left"]),
        ("right", right_poly, trace["right"]),
        ("out", out_poly, trace["out"]),
        ("op", op_poly, trace["op"]),
    ]:
        for _i in range(2):
            _v = _poly(_i)
            _e = _col[_i]
            _status = "✓" if _v == _e else "✗"
            print(f"  {_name}~({_i}) = {_v}  (expected {_e}) {_status}")
    return left_poly, op_poly, out_poly, right_poly


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 4: The Constraint Polynomial

    Now here's where it gets interesting. The CPU has a **rule**: at every cycle, the output
    must be correct. The constraint is:

    $$\text{out}(t) = (1 - \text{op}(t)) \cdot \text{left}(t) \cdot \text{right}(t) + \text{op}(t) \cdot (\text{left}(t) + \text{right}(t))$$

    - When op=0 (MUL): out = left * right
    - When op=1 (ADD): out = left + right

    If the trace is valid, this constraint holds at **every boolean point** (every cycle).
    Let's check:
    """)
    return


@app.cell
def _(add, left_poly, mul, op_poly, out_poly, right_poly, sub):
    def constraint_poly(x):
        """
        Returns 0 if the constraint is satisfied at point x.
        C(x) = out(x) - [(1-op(x))·left(x)·right(x) + op(x)·(left(x)+right(x))]
        """
        _l = left_poly(x)
        _r = right_poly(x)
        _o = out_poly(x)
        _op = op_poly(x)

        _mul_result = mul(_l, _r)  # left * right
        _add_result = add(_l, _r)  # left + right

        # (1-op)·mul_result + op·add_result
        _expected = add(mul(sub(1, _op), _mul_result), mul(_op, _add_result))

        return sub(_o, _expected)  # should be 0 if valid

    # Check on boolean points (the actual cycles)
    print("Constraint check on each cycle:")
    for _t in range(2):
        _c = constraint_poly(_t)
        print(f"  C({_t}) = {_c}  {'✓ satisfied!' if _c == 0 else '✗ VIOLATION!'}")

    # What about a random point? If the trace is valid, the constraint polynomial
    # is the zero polynomial... so it should be 0 EVERYWHERE.
    _r = 42
    _val_random = constraint_poly(_r)
    print(f"\n  C({_r}) = {_val_random}  (random point... is it still 0?)")

    if _val_random == 0:
        print("  ✓ Zero everywhere! The constraint polynomial is identically zero.")
    else:
        print(f"  It's {_val_random}, not 0. The constraint polynomial has degree > 1")
        print(
            "(because of the multiplication left·right, the MLE structure doesn't guarantee"
        )
        print("  that the constraint poly is zero beyond the hypercube)")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Key Insight: Why Sumcheck?

    The constraint polynomial is **zero on the boolean hypercube** (on actual cycles), but might not be zero elsewhere. That's fine, we only care about the boolean points.

    The verifier wants to check:

    $$\sum_{x \in \{0,1\}^n} C(x) = 0$$

    This is exactly what **sumcheck** does! It turns "check a sum over $2^n$ points" into "check one evaluation at a random point", in $n$ interactive rounds.

    For our toy example with $n=1$, sumcheck is trivially one round. But the structure scales: a real Jolt trace with T=65536 cycles uses $n=16$ variables and 16 sumcheck rounds, and the verifier never touches the $2^{16}$ individual rows.

    ---

    ## Summary

    | Concept | Concrete Example |
    |---------|-----------------|
    | Program | `output = a*b + c` |
    | Execution trace | 2 cycles x 4 wires = 8 field elements |
    | Column -> polynomial | `left~(x) = 3 + 12x` over F_97 |
    | Constraint | `out = (1-op)·left·right + op·(left+right)` |
    | Validity check | C(x) = 0 for all x in {0,1}^1 |
    | What sumcheck proves | Sum of C(x) = 0 without checking each row |

    **Next**: Exercise 2 will run sumcheck on this constraint to see how the
    verifier checks validity with just one random evaluation.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---

    ## Exercises (try before moving on!)

    **1.** What happens if the prover lies and sets `out[0] = 16` instead of 15? Modify the trace above and re-run. Does the constraint check catch it?

    > The constraint check catches it at cycle 0: `C(0) = 1 ✗ VIOLATION!` (because 16 - 15 = 1), while `C(1) = 0 ✓ satisfied!`. The lie shows up exactly where the wrong value was placed.

    **2.** Compute `right~(50)` by hand. The values are [5, 7], so: `right~(x) = 5·(1-x) + 7·x = 5 + 2x`. What's `right~(50) mod 97`?

    $$\text{right}~(50) = 5 + 2 \times 50 \mod 97 = 8$$


    **3.** Why can't we just check `C(0) + C(1) = 0` directly without sumcheck?
    Because a cheating prover can make the sum cancel to zero even with invalid constraints. In F_97, if the prover submits a bad trace where:

      C(0) = 5    ← constraint violated at cycle 0
      C(1) = 92   ← constraint violated at cycle 1

    Then C(0) + C(1) = 5 + 92 = 97 = 0 mod 97. The sum is zero, but neither constraint is satisfied. The violations cancel out.

    What sumcheck does differently is that it doesn't just check the sum. It introduces a random challenge r and ultimately checks C(r) at a random point. A cheating prover would need to make C zero at a point they can't predict in advance. By Schwartz-Zippel, a nonzero degree-d polynomial has at most d roots out of 97 possible values — so the chance of getting lucky is tiny (d/97 in our toy field, d/2²⁵⁴ in real systems).

    The sum check Σ C(x) = 0 is just the starting claim. The protocol then reduces it to a single random evaluation, which is what actually provides soundness.
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
