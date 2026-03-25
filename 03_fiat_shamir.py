import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Exercise 3: Fiat-Shamir. Making Sumcheck Non-Interactive

    **Goal**: Replace the interactive verifier (who picks random challenges) with a hash function, so the prover can generate the entire proof alone and anyone can verify it later.

    ---

    ## The problem with interactive sumcheck

    In Exercise 2, the protocol was a **conversation**:

    ```
    Prover → sends s1          → Verifier
    Prover ← receives r1 = 23  ← Verifier (picks randomly)
    Prover → sends s2          → Verifier
    Prover ← receives r2 = 71  ← Verifier (picks randomly)
    ```

    This requires the verifier to be online, picking fresh random challenges. That's fine in theory, but useless for blockchains, you need a proof you can post once and anyone can check later.

    ## The Fiat-Shamir trick

    Replace "verifier picks random r" with "hash everything so far to get r":

    ```
    r1 = Hash(s1)
    r2 = Hash(s1, r1, s2)
    ```

    The challenges are now **deterministic**, so anyone can recompute them from the proof. But they're still **unpredictable to the prover** at the time they choose s1, because they can't control the hash output.

    This is called the **Fiat-Shamir heuristic** (or transform).
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


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 1: A toy hash function (the "transcript")

    In real Jolt, the hash is **Poseidon** (a ZK-friendly hash over prime fields). We'll use **SHA-256**, just because it is in Python standard lib. The structure is the same as Poseidon: absorb values, squeeze challenges.

    The transcript maintains a running **state** that absorbs values and squeezes challenges:

    ```
    absorb(value):  state = hash(state, value)
    squeeze():      challenge = hash(state, "challenge"); return challenge
    ```

    Every value the prover sends gets absorbed. Every challenge gets squeezed. The state is a chain, changing any earlier value changes all later challenges.
    """)
    return


@app.cell
def _(P):
    import hashlib

    class Transcript:
        """
        Fiat-Shamir transcript over F_97 using SHA-256.

        Same structure as Poseidon in real Jolt:
        - absorb() feeds values into a running hash state
        - squeeze() derives a pseudorandom challenge
        """

        def __init__(self):
            self.state = b""  # running byte state

        def absorb(self, value):
            """Feed a field element into the transcript."""
            # Append the value's bytes to the state, then hash
            self.state = hashlib.sha256(
                self.state + value.to_bytes(8, "little")
            ).digest()

        def squeeze(self):
            """Derive a pseudorandom challenge from the current state."""
            # Hash state with a domain separator to get the challenge
            _digest = hashlib.sha256(self.state + b"challenge").digest()
            # Convert to a field element: interpret as integer, take mod P
            _challenge = int.from_bytes(_digest, "little") % P
            # Update state so next squeeze gives a different value
            self.state = _digest
            return _challenge

        def absorb_many(self, values):
            """Absorb a list of values."""
            for _v in values:
                self.absorb(_v)

    # Demo: same inputs → same outputs (deterministic)
    _t1 = Transcript()
    _t1.absorb(10)
    _t1.absorb(20)
    _c1 = _t1.squeeze()

    _t2 = Transcript()
    _t2.absorb(10)
    _t2.absorb(20)
    _c2 = _t2.squeeze()

    print("Determinism check:")
    print(f"  Transcript 1: absorb(10), absorb(20), squeeze() = {_c1}")
    print(f"  Transcript 2: absorb(10), absorb(20), squeeze() = {_c2}")
    print(f"  Same? {_c1 == _c2} ✓")

    # But different inputs → different outputs
    _t3 = Transcript()
    _t3.absorb(10)
    _t3.absorb(21)  # changed!
    _c3 = _t3.squeeze()
    print(f"\n  Transcript 3: absorb(10), absorb(21), squeeze() = {_c3}")
    print(f"  Different from transcript 1? {_c1 != _c3} ✓")
    return (Transcript,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 2: Rebuild the sumcheck setup

    Same 4-cycle trace and constraint from Exercise 2.
    """)
    return


@app.cell
def _(P, add, mul, sub):
    def eq_factor(x, b):
        if b == 0:
            return sub(1, x)
        else:
            return x

    def make_mle_2var(values):
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
def _(add, make_mle_2var, mul, sub):
    _trace = {
        "left": [3, 15, 22, 88],
        "right": [5, 7, 4, 0],
        "out": [15, 22, 88, 88],
        "op": [0, 1, 0, 1],
    }

    _left_poly = make_mle_2var(_trace["left"])
    _right_poly = make_mle_2var(_trace["right"])
    _out_poly = make_mle_2var(_trace["out"])
    _op_poly = make_mle_2var(_trace["op"])

    def C(x1, x2):
        _l = _left_poly(x1, x2)
        _r = _right_poly(x1, x2)
        _o = _out_poly(x1, x2)
        _op = _op_poly(x1, x2)
        _mul_res = mul(_l, _r)
        _add_res = add(_l, _r)
        _expected = add(mul(sub(1, _op), _mul_res), mul(_op, _add_res))
        return sub(_o, _expected)

    return (C,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 3: Non-interactive sumcheck (prover side)

    The prover generates the **entire proof** alone. No interaction needed.

    At each round, instead of waiting for the verifier to send a random challenge,
    the prover:
    1. Computes the round polynomial
    2. Absorbs its evaluations into the transcript
    3. Squeezes a challenge from the transcript

    The key insight: **the challenges are derived from the prover's own messages**.
    The prover can't "shop" for good challenges because changing s1 changes r1,
    which changes everything downstream.
    """)
    return


@app.cell
def _(C, Transcript, add):
    # ========== PROVER ==========
    prover_transcript = Transcript()

    # Round 1: compute s1, absorb it, squeeze r1
    def _s1(X):
        return add(C(X, 0), C(X, 1))

    # Evaluate s1 at points 0, 1, 2, 3 (degree ≤ 3, need 4 points)
    s1_evals = [_s1(0), _s1(1), _s1(2), _s1(3)]

    # Absorb all evaluations into transcript
    prover_transcript.absorb_many(s1_evals)

    # Squeeze challenge r1 — determined by s1_evals
    r1 = prover_transcript.squeeze()

    print("=== PROVER: Round 1 ===")
    print(f"  s1 evaluations: {s1_evals}")
    print(f"  r1 (from hash): {r1}")

    # Round 2: compute s2 using r1, absorb it, squeeze r2
    def _s2(X):
        return C(r1, X)

    s2_evals = [_s2(0), _s2(1), _s2(2), _s2(3)]

    prover_transcript.absorb_many(s2_evals)
    r2 = prover_transcript.squeeze()

    print(f"\n=== PROVER: Round 2 ===")
    print(f"  s2 evaluations: {s2_evals}")
    print(f"  r2 (from hash): {r2}")

    # The proof is just the evaluations, the verifier can recompute everything else
    proof = {
        "s1_evals": s1_evals,
        "s2_evals": s2_evals,
    }
    print(f"\n=== PROOF (what gets sent) ===")
    print(f"  {proof}")
    print(f"  Total: {len(s1_evals) + len(s2_evals)} field elements")
    return (proof,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 4: Non-interactive verification

    The verifier receives only the **proof** (the round polynomial evaluations).
    They reconstruct everything else: challenges, consistency checks, final evaluation.

    The verifier runs the **exact same transcript** as the prover. Since both absorb
    the same values, they squeeze the same challenges. No communication needed.
    """)
    return


@app.cell
def _(C, P, Transcript, add, proof):
    # ========== VERIFIER ==========
    # The verifier only has the proof, they recompute everything else
    _s1_evals = proof["s1_evals"]
    _s2_evals = proof["s2_evals"]

    verifier_transcript = Transcript()
    print("=== VERIFIER ===\n")

    # --- Round 1 ---
    # Check: s1(0) + s1(1) = 0 (the known claim)
    _sum_check_1 = add(_s1_evals[0], _s1_evals[1])
    print(f"Round 1: s1(0) + s1(1) = {_s1_evals[0]} + {_s1_evals[1]} = {_sum_check_1}")
    print(f"  Expected: 0")
    _ok1 = _sum_check_1 == 0
    print(f"  {'✓ Pass' if _ok1 else '✗ FAIL'}")

    # Absorb s1 evaluations and squeeze r1 (same as prover did)
    verifier_transcript.absorb_many(_s1_evals)
    _v_r1 = verifier_transcript.squeeze()
    print(f"  r1 (recomputed from hash): {_v_r1}")

    # Evaluate s1 at r1 using Lagrange interpolation
    def lagrange_eval(evals, x):
        """Evaluate polynomial through points (0,e0),(1,e1),(2,e2),(3,e3) at x."""
        _n = len(evals)
        _result = 0
        for _i in range(_n):
            _basis = 1
            for _j in range(_n):
                if _i != _j:
                    # basis_i(x) = product of (x - j) / (i - j) for j != i
                    _num = (x - _j) % P
                    _den = (_i - _j) % P
                    _den_inv = pow(_den, P - 2, P)
                    _basis = (_basis * _num % P) * _den_inv % P
            _result = (_result + evals[_i] * _basis) % P
        return _result

    _s1_at_r1 = lagrange_eval(_s1_evals, _v_r1)
    print(f"  s1({_v_r1}) = {_s1_at_r1}  (via Lagrange interpolation)")

    # --- Round 2 ---
    _sum_check_2 = add(_s2_evals[0], _s2_evals[1])
    print(
        f"\nRound 2: s2(0) + s2(1) = {_s2_evals[0]} + {_s2_evals[1]} = {_sum_check_2}"
    )
    print(f"  Expected: s1(r1) = {_s1_at_r1}")
    _ok2 = _sum_check_2 == _s1_at_r1
    print(f"  {'✓ Pass' if _ok2 else '✗ FAIL'}")

    # Absorb s2 evaluations and squeeze r2
    verifier_transcript.absorb_many(_s2_evals)
    _v_r2 = verifier_transcript.squeeze()
    print(f"  r2 (recomputed from hash): {_v_r2}")

    # Evaluate s2 at r2
    _s2_at_r2 = lagrange_eval(_s2_evals, _v_r2)
    print(f"  s2({_v_r2}) = {_s2_at_r2}  (via Lagrange interpolation)")

    # --- Final check ---
    # Verifier evaluates C(r1, r2) directly (or gets it from an oracle)
    _actual = C(_v_r1, _v_r2)
    _ok3 = _s2_at_r2 == _actual
    print(f"\nFinal check: C({_v_r1}, {_v_r2})")
    print(f"  Claimed (from s2): {_s2_at_r2}")
    print(f"  Actual:            {_actual}")
    print(f"  {'✓ Pass' if _ok3 else '✗ FAIL'}")

    _all_pass = _ok1 and _ok2 and _ok3
    print(f"\n{'=' * 40}")
    print(f"{'✓ PROOF VERIFIED!' if _all_pass else '✗ PROOF REJECTED!'}")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## What just happened?

    ```
    PROVER (alone, offline)              VERIFIER (alone, later)
    ─────────────────────                ────────────────────────
    compute s1                           receive proof = {s1_evals, s2_evals}
    absorb s1 into transcript            absorb s1 into transcript
    r1 = squeeze()                       r1 = squeeze()  ← SAME r1!
    compute s2 (using r1)                check s1(0)+s1(1) = 0
    absorb s2 into transcript            interpolate s1(r1)
    r2 = squeeze()                       check s2(0)+s2(1) = s1(r1)
                                         absorb s2 into transcript
    send proof = {s1_evals, s2_evals}    r2 = squeeze()  ← SAME r2!
                                         check C(r1,r2) = s2(r2)
    ```

    Both sides run the **exact same transcript**. The prover can't cheat because:

    1. The challenges are **deterministic**: anyone can recompute them from the proof
    2. The challenges are **unpredictable**: changing any prover message changes all subsequent challenges
    3. The proof is **self-contained**: no interaction needed, verify anytime

    This is how Jolt works: the prover generates a proof offline, posts it on-chain, and the smart contract (verifier) replays the transcript to check it.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The transcript is a chain

    This is why **transcript continuity** matters so much in Jolt.
    Every value absorbed changes all future challenges:

    ```
    absorb(s1) → state₁ → squeeze → r1
                                      ↓
    absorb(s2) → state₂ → squeeze → r2    (depends on r1, which depends on s1)
                                      ↓
    absorb(s3) → state₃ → squeeze → r3    (depends on everything above)
    ```

    If someone starts a **fresh transcript** (state=0) in the middle, they can
    predict future challenges and forge proofs. This is exactly the security bug
    that was fixed in Jolt's recursion (the recursion transcript must continue
    from stages 1-7's final state, not start from zero).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---

    ## Exercises

    **1.** The proof is `{s1_evals, s2_evals}`, 8 field elements total. Could the verifier check the proof with **fewer** values? What's the minimum the prover needs to send? *(Hint: the verifier knows `s1(0) + s1(1) = 0`, so one of those is redundant...)*

    > Yes, **6 instead of 8**. The verifier knows `s1(0) + s1(1) = 0`, so `s1(1) = -s1(0)`, no need to send both. Same for round 2: `s2(0) + s2(1) = s1(r1)` means `s2(1)` is redundant. So you send 3 per round instead of 4. This is exactly the **compressed univariate** optimization that real Jolt uses.

    **2.** What happens if the prover tries to tamper with `s1_evals[2]`? Try changing it in the proof dict and re-running the verifier. Which check fails?

    > The tampered value gets absorbed into the transcript, so `r1` changes (different hash input -> different challenge). Then `s1(r1)` via Lagrange interpolation gives a wrong value. Round 2's consistency check `s2(0) + s2(1) = s1(r1)` will fail — unless the prover also tampers with s2, but then `r2` changes and the final check `C(r1, r2) = s2(r2)` fails. The chain of hashes means you can't tamper with anything without breaking something downstream.

    **3.** We use SHA-256 here, which is a real cryptographic hash. Jolt uses **Poseidon** instead. Why? What makes Poseidon better suited for ZK circuits, even though SHA-256 is perfectly secure?

    > **Circuit cost.** When the verifier runs inside a Groth16 circuit (the whole point of transpilation), every hash becomes constraints. SHA-256 costs ~25,000 constraints per hash (lots of bitwise operations). Poseidon costs ~250 constraints per hash (designed as native field arithmetic, just additions and multiplications). Since the Jolt verifier hashes hundreds of times across 7 stages, that's millions of extra constraints with SHA-256 vs tens of thousands with Poseidon. Poseidon is ~100x cheaper in-circuit.

    **4.** The verifier uses Lagrange interpolation to evaluate `s1(r1)` from 4 points. Could they instead receive the polynomial **coefficients** directly? What are the tradeoffs?

    > Yes, both work. **Evaluations** (what we do here): the verifier needs Lagrange interpolation to evaluate at `r`, but the values are conceptually simple. **Coefficients**: the verifier evaluates directly via Horner's method (cheaper), but the prover converts from evaluations to coefficients first. Jolt actually sends **compressed coefficients**, all coefficients except the linear term, which the verifier recovers from the `s(0)+s(1)=claim` constraint. This is the `CompressedUniPoly` optimization.

    **Next**: Exercise 4 will introduce **symbolic execution**, running the same verifier code with symbolic values to record the operations as a circuit.
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
