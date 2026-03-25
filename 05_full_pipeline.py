import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Exercise 5: The Full Pipeline

    **Goal**: Run the complete pipeline end-to-end, from program execution to circuit verification.

    This notebook combines everything from Exercises 1-4:

    ```
    Program  ->  Trace  ->  Polynomials  ->  Sumcheck Proof (prover)
                                                      |
                                                      v
                              Circuit  <-  Symbolic Verifier  <-  Fiat-Shamir
                                |
                                v
                          Verify with Witness (= "Groth16")
    ```

    We'll see each step produce concrete output that feeds into the next.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Phase 1: The Field
    """)
    return


@app.cell
def _():
    import hashlib

    P = 97

    def f_add(a, b):
        return (a + b) % P

    def f_sub(a, b):
        return (a - b) % P

    def f_mul(a, b):
        return (a * b) % P

    def f_inv(a):
        return pow(a, P - 2, P)

    return P, f_add, f_mul, f_sub, hashlib


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Phase 2: Program Execution -> Trace

    Our program: `result = ((3 * 5) + 7) * 4 = 88`

    The CPU executes it in 4 cycles. This trace is the **witness**.
    """)
    return


@app.cell
def _():
    trace = {
        "left":  [3, 15, 22, 88],
        "right": [5,  7,  4,  0],
        "out":   [15, 22, 88, 88],
        "op":    [0,  1,  0,  1],  # 0=MUL, 1=ADD
    }

    print("EXECUTION TRACE:")
    print("  Cycle | Op  | Left | Right | Out")
    print("  ------+-----+------+-------+----")
    for _i in range(4):
        _op = "MUL" if trace["op"][_i] == 0 else "ADD"
        print(f"    {_i}   | {_op} |  {trace['left'][_i]:2d}  |   {trace['right'][_i]:2d}  | {trace['out'][_i]:2d}")
    return (trace,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Phase 3: Trace -> Polynomials (MLEs)

    Each column becomes a multilinear polynomial in 2 variables.
    """)
    return


@app.cell
def _(P, f_add, f_mul, f_sub):
    def eq_factor(x, b):
        if b == 0:
            return f_sub(1, x)
        return x

    def make_mle(values):
        _v = [val % P for val in values]

        def mle(x1, x2):
            _total = 0
            for _b1 in range(2):
                for _b2 in range(2):
                    _idx = _b1 * 2 + _b2
                    _eq = f_mul(eq_factor(x1, _b1), eq_factor(x2, _b2))
                    _total = f_add(_total, f_mul(_v[_idx], _eq))
            return _total

        return mle

    return (make_mle,)


@app.cell
def _(f_add, f_mul, f_sub, make_mle, trace):
    left_p = make_mle(trace["left"])
    right_p = make_mle(trace["right"])
    out_p = make_mle(trace["out"])
    op_p = make_mle(trace["op"])

    def C(x1, x2):
        """Constraint polynomial: 0 iff the cycle is valid."""
        _l = left_p(x1, x2)
        _r = right_p(x1, x2)
        _o = out_p(x1, x2)
        _op = op_p(x1, x2)
        _expected = f_add(
            f_mul(f_sub(1, _op), f_mul(_l, _r)),
            f_mul(_op, f_add(_l, _r)),
        )
        return f_sub(_o, _expected)

    # Verify constraint is zero on all boolean points
    print("CONSTRAINT CHECK:")
    for _b1 in range(2):
        for _b2 in range(2):
            _v = C(_b1, _b2)
            print(f"  C({_b1},{_b2}) = {_v}  {'✓' if _v == 0 else '✗'}")
    return (C,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Phase 4: Prover generates sumcheck proof

    The prover computes the round polynomials and derives challenges via Fiat-Shamir.
    The output is the **proof**: just the polynomial evaluations.
    """)
    return


@app.cell
def _(P, hashlib):
    class Transcript:
        def __init__(self):
            self.state = b""

        def absorb(self, value):
            self.state = hashlib.sha256(
                self.state + value.to_bytes(8, "little")
            ).digest()

        def absorb_many(self, values):
            for _v in values:
                self.absorb(_v)

        def squeeze(self):
            _digest = hashlib.sha256(self.state + b"challenge").digest()
            _challenge = int.from_bytes(_digest, "little") % P
            self.state = _digest
            return _challenge

    return (Transcript,)


@app.cell
def _(C, Transcript, f_add):
    # ========== PROVER ==========
    _pt = Transcript()

    # Round 1: s1(X) = C(X,0) + C(X,1), evaluated at X = 0,1,2,3
    def _s1(X):
        return f_add(C(X, 0), C(X, 1))

    proof_s1 = [_s1(0), _s1(1), _s1(2), _s1(3)]
    _pt.absorb_many(proof_s1)
    proof_r1 = _pt.squeeze()

    # Round 2: s2(X) = C(r1, X), evaluated at X = 0,1,2,3
    def _s2(X):
        return C(proof_r1, X)

    proof_s2 = [_s2(0), _s2(1), _s2(2), _s2(3)]
    _pt.absorb_many(proof_s2)
    proof_r2 = _pt.squeeze()

    # Final claim: C(r1, r2)
    proof_c_final = C(proof_r1, proof_r2)

    # The proof = round polynomial evaluations + final evaluation
    proof = {
        "s1_evals": proof_s1,
        "s2_evals": proof_s2,
        "c_final": proof_c_final,
    }

    print("PROVER OUTPUT:")
    print(f"  s1 evals: {proof_s1}")
    print(f"  r1 (from SHA-256): {proof_r1}")
    print(f"  s2 evals: {proof_s2}")
    print(f"  r2 (from SHA-256): {proof_r2}")
    print(f"  C(r1, r2) = {proof_c_final}")
    print(f"\n  Proof size: {len(proof_s1) + len(proof_s2) + 1} field elements")
    return (proof,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Phase 5: Symbolic Execution of the Verifier

    Now the key step. We run the **verifier** with symbolic values to capture the circuit.

    The verifier receives the proof, replays the Fiat-Shamir transcript,
    and checks consistency. Running it symbolically records every operation
    as an AST node and every assertion as a constraint.
    """)
    return


@app.cell
def _(P):
    # --- Symbolic field type ---
    sym_arena = []
    sym_constraints = []

    class Sym:
        """Symbolic field element. Records ops instead of computing."""

        def __init__(self, node):
            sym_arena.append(node)
            self.nid = len(sym_arena) - 1

        def __add__(self, other):
            return Sym(("Add", self.nid, other.nid))

        def __sub__(self, other):
            return Sym(("Sub", self.nid, other.nid))

        def __mul__(self, other):
            return Sym(("Mul", self.nid, other.nid))

        def __eq__(self, other):
            _diff = self - other
            sym_constraints.append(_diff.nid)
            return True

        def __repr__(self):
            return f"N{self.nid}"

    # --- Symbolic transcript (uses real SHA-256, but over symbolic nodes) ---
    import hashlib as _hl

    class SymTranscript:
        """
        Transcript that absorbs symbolic variables and squeezes
        symbolic challenges. Internally uses real SHA-256 on the
        witness values to get deterministic challenge values,
        then wraps them as Sym constants.

        In real Jolt, this is PoseidonAstTranscript — it creates
        Poseidon hash nodes in the arena. We simplify by computing
        the hash concretely and injecting the result as a constant.
        """

        def __init__(self):
            self.state = b""

        def absorb(self, witness_value):
            self.state = _hl.sha256(
                self.state + witness_value.to_bytes(8, "little")
            ).digest()

        def absorb_many(self, witness_values):
            for _v in witness_values:
                self.absorb(_v)

        def squeeze(self):
            _digest = _hl.sha256(self.state + b"challenge").digest()
            _challenge = int.from_bytes(_digest, "little") % P
            self.state = _digest
            return _challenge

    return Sym, SymTranscript, sym_arena, sym_constraints


@app.cell
def _(P, Sym, SymTranscript, proof, sym_arena, sym_constraints):
    # Clear arena
    sym_arena.clear()
    sym_constraints.clear()

    # ========== SYMBOLIC VERIFIER ==========
    # This is the code that would become stages_circuit.go in Jolt

    # Create symbolic variables for all proof data (the witness)
    w_s1 = [Sym(("Var", f"s1_{_i}")) for _i in range(4)]  # Nodes 0-3
    w_s2 = [Sym(("Var", f"s2_{_i}")) for _i in range(4)]  # Nodes 4-7
    w_c_final = Sym(("Var", "c_final"))                     # Node 8

    # Replay Fiat-Shamir with concrete values to get challenges
    _vt = SymTranscript()
    _vt.absorb_many(proof["s1_evals"])
    challenge_r1 = _vt.squeeze()
    _vt.absorb_many(proof["s2_evals"])
    challenge_r2 = _vt.squeeze()

    # --- Lagrange interpolation (symbolic) ---
    # Evaluate polynomial through (0,e0),(1,e1),(2,e2),(3,e3) at point r
    # The Lagrange basis values are CONCRETE (computed from the challenge),
    # but the polynomial evaluations are SYMBOLIC (from the witness).
    def sym_lagrange_eval(sym_evals, r_concrete):
        """
        Symbolically evaluate a polynomial given as 4 symbolic evaluation points
        at a concrete challenge point r.
        Returns a symbolic expression.
        """
        # Precompute concrete Lagrange basis values
        _bases = []
        for _i in range(4):
            _b = 1
            for _j in range(4):
                if _i != _j:
                    _num = (r_concrete - _j) % P
                    _den = (_i - _j) % P
                    _den_inv = pow(_den, P - 2, P)
                    _b = (_b * _num * _den_inv) % P
            _bases.append(_b)

        # Build symbolic expression: sum of basis_i * eval_i
        _result = None
        for _i in range(4):
            _coeff = Sym(("Const", _bases[_i]))
            _term = _coeff * sym_evals[_i]
            if _result is None:
                _result = _term
            else:
                _result = _result + _term
        return _result

    # ====== CONSTRAINT 1: Round 1 consistency ======
    # s1(0) + s1(1) == 0
    _sym_zero = Sym(("Const", 0))
    _round1_sum = w_s1[0] + w_s1[1]
    assert _round1_sum == _sym_zero

    # ====== CONSTRAINT 2: Round 2 consistency ======
    # s2(0) + s2(1) == s1(r1)  (via Lagrange interpolation)
    _s1_at_r1 = sym_lagrange_eval(w_s1, challenge_r1)
    _round2_sum = w_s2[0] + w_s2[1]
    assert _round2_sum == _s1_at_r1

    # ====== CONSTRAINT 3: Final evaluation ======
    # s2(r2) == c_final  (via Lagrange interpolation)
    _s2_at_r2 = sym_lagrange_eval(w_s2, challenge_r2)
    assert _s2_at_r2 == w_c_final

    print("SYMBOLIC EXECUTION COMPLETE:")
    print(f"  Arena: {len(sym_arena)} nodes")
    print(f"  Constraints: {len(sym_constraints)}")
    print(f"  Challenges: r1={challenge_r1}, r2={challenge_r2}")
    print(f"\n  Witness variables: 9 (s1[0..3], s2[0..3], c_final)")
    print(f"  Internal nodes: {len(sym_arena) - 9}")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Phase 6: Code Generation

    Walk the arena and emit circuit code. This is what `gnark_codegen.rs` does in Jolt.
    """)
    return


@app.cell
def _(sym_arena, sym_constraints):
    print("GENERATED CIRCUIT:")
    print("=" * 60)
    print("func (c *Circuit) Define(api frontend.API) error {")

    for _i, _node in enumerate(sym_arena):
        _op = _node[0]
        if _op == "Var":
            print(f"    // n{_i} = circuit.{_node[1]}")
        elif _op == "Const":
            print(f"    n{_i} := frontend.Variable({_node[1]})")
        elif _op in ("Add", "Sub", "Mul"):
            print(f"    n{_i} := api.{_op}(n{_node[1]}, n{_node[2]})")

    print()
    for _i, _c in enumerate(sym_constraints):
        print(f"    api.AssertIsEqual(n{_c}, 0)  // constraint {_i}")

    print("    return nil")
    print("}")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Phase 7: Verify with Witness ("Groth16")

    In real Groth16, the prover uses the circuit + witness to generate a 164-byte proof.
    Here, we'll do the equivalent: **evaluate every arena node with the concrete witness
    values and check that all constraints equal zero.**

    If this passes, it means the circuit is satisfiable with this witness —
    the same thing Groth16 proves, just without the cryptography.
    """)
    return


@app.cell
def _(P, proof, sym_arena, sym_constraints):
    # Build witness map: variable name -> concrete value
    _witness = {
        "s1_0": proof["s1_evals"][0],
        "s1_1": proof["s1_evals"][1],
        "s1_2": proof["s1_evals"][2],
        "s1_3": proof["s1_evals"][3],
        "s2_0": proof["s2_evals"][0],
        "s2_1": proof["s2_evals"][1],
        "s2_2": proof["s2_evals"][2],
        "s2_3": proof["s2_evals"][3],
        "c_final": proof["c_final"],
    }

    # Evaluate every node in the arena with concrete values
    _values = [0] * len(sym_arena)

    print("CIRCUIT EVALUATION WITH WITNESS:")
    print("=" * 60)

    for _i, _node in enumerate(sym_arena):
        _op = _node[0]
        if _op == "Var":
            _values[_i] = _witness[_node[1]]
        elif _op == "Const":
            _values[_i] = _node[1] % P
        elif _op == "Add":
            _values[_i] = (_values[_node[1]] + _values[_node[2]]) % P
        elif _op == "Sub":
            _values[_i] = (_values[_node[1]] - _values[_node[2]]) % P
        elif _op == "Mul":
            _values[_i] = (_values[_node[1]] * _values[_node[2]]) % P

    # Check all constraints
    _all_pass = True
    print("\nConstraint checks:")
    for _i, _c in enumerate(sym_constraints):
        _v = _values[_c]
        _ok = _v == 0
        if not _ok:
            _all_pass = False
        print(f"  Constraint {_i}: node n{_c} = {_v}  {'✓' if _ok else '✗ FAIL'}")

    print(f"\n{'=' * 60}")
    if _all_pass:
        print("✓ ALL CONSTRAINTS SATISFIED — PROOF WOULD VERIFY!")
        print(f"  Circuit size: {len(sym_arena)} nodes, {len(sym_constraints)} constraints")
        print(f"  Witness size: {len(_witness)} field elements")
        print(f"  In real Groth16: this becomes a 164-byte proof")
    else:
        print("✗ CONSTRAINT VIOLATION — PROOF WOULD BE REJECTED!")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## The Complete Pipeline

    Here's everything that just happened:

    ```
    Phase 1: Field arithmetic (F_97)
        |
    Phase 2: Program execution -> trace (4 cycles x 4 wires)
        |
    Phase 3: Trace columns -> MLE polynomials (2 variables each)
        |
    Phase 4: PROVER runs sumcheck
        |     - computes round polynomials s1, s2
        |     - derives challenges via SHA-256 transcript
        |     - outputs proof = {s1_evals, s2_evals, c_final}
        |
    Phase 5: SYMBOLIC EXECUTION of verifier
        |     - same verification logic, but with Sym instead of int
        |     - captures ~40 arena nodes and 3 constraints
        |     - this is what Jolt's transpiler does
        |
    Phase 6: CODE GENERATION
        |     - walk arena -> emit gnark API calls
        |     - constraints -> api.AssertIsEqual()
        |     - this is gnark_codegen.rs
        |
    Phase 7: VERIFY with witness
              - evaluate arena with concrete proof values
              - check all constraints = 0
              - equivalent to Groth16 prove + verify
    ```

    ---

    ## How this maps to real Jolt

    | Our toy pipeline | Real Jolt |
    |-----------------|-----------|
    | 4-cycle trace | 65536-cycle RISC-V trace |
    | 4 columns, 1 constraint | ~40 polynomial types, 5 properties |
    | 2 sumcheck rounds | ~100+ rounds across 7 stages |
    | SHA-256 transcript | Poseidon transcript |
    | `Sym` class | `MleAst` type |
    | `sym_arena` list | `NODE_ARENA` global Vec |
    | `assert ==` captures constraint | `PartialEq::eq` in constraint mode |
    | Print gnark pseudocode | `gnark_codegen.rs` emits Go |
    | Evaluate arena with witness | gnark Groth16 prove + verify |
    | 3 constraints | 17 assertions (2.86M R1CS constraints) |
    | ~40 arena nodes | Millions of arena nodes |
    | 9 witness values | Thousands of witness values |
    | All in F_97 | All in F_r (BN254, 254-bit prime) |

    The **structure is identical**. The scale is different.

    ---

    ## What Groth16 adds

    Our Phase 7 just evaluates the circuit directly. Real Groth16 does something
    much more powerful: it generates a **164-byte proof** that the circuit is satisfiable,
    without revealing the witness. The verifier checks the proof in ~3ms without
    ever seeing the witness values.

    This is what makes it useful for blockchains: post the 164-byte proof on-chain,
    the smart contract verifies it for ~250K gas, and nobody learns the execution trace.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Final Exercises

    **1.** Corrupt one witness value (e.g., change `s1_evals[0]`) in the proof and re-run. Which constraint fails? Why?

    > Constraint 0 (round 1 consistency) fails, because `s1(0) + s1(1)` no longer equals 0. Constraints 1 and 2 likely also fail, because the Lagrange interpolation `s1(r1)` depends on all four `s1` evaluation points, changing one changes the interpolated value, making `s2(0) + s2(1) != s1(r1)`. Note: in our notebook, the challenges (r1, r2) are baked into the circuit as constants during symbolic execution, so they don't change. The corruption cascades through the **Lagrange interpolation** (which references the symbolic witness variables), not through re-hashing.

    **2.** Count the arena nodes that are `Mul` operations. In Groth16, each multiplication roughly corresponds to one R1CS constraint. How many "Groth16 constraints" does our toy circuit have?

    > Count the `Mul` nodes in the arena printout. There are **8** multiplications (the Lagrange interpolation does `Const * Var` for each of the 4 basis values, twice, once for `s1` and once for `s2`). So our toy circuit has roughly 8 R1CS constraints. Compared to Jolt's 2.86M, same structure, vastly different scale.

    **3.** In real Jolt, the symbolic Poseidon hash creates hundreds of additional arena nodes per hash call (additions and multiplications implementing the Poseidon permutation). If there are ~200 hash calls across 7 stages, and each creates ~250 nodes, how many arena nodes come from hashing alone?

    > 200 x 250 = **50,000 nodes** just from hashing. That's a significant chunk of the total arena, and it's why Poseidon (~250 constraints/hash) was chosen over SHA-256 (~25,000 constraints/hash). With SHA-256, hashing alone would produce 200 x 25,000 = 5,000,000 nodes, more than the entire current circuit.

    **4.** The proof has 9 field elements (4 + 4 + 1). In real Jolt, the proof is much larger (thousands of field elements for sumcheck round polynomials across 7 stages). But the Groth16 proof is always 164 bytes. Why doesn't proof size grow with circuit size?

    > Groth16 is a **succinct** proof system. The proof is always 3 group elements (2 G1 points + 1 G2 point on BN254), which gnark serializes to 164 bytes regardless of circuit size. The Jolt proof (sumcheck polynomials, commitments, etc.) is the **witness** to the Groth16 circuit, it goes into the prover, not into the proof. The Groth16 proof attests that "there exists a witness satisfying all 2.86M constraints" without revealing the witness itself. Circuit size affects **proving time**, not proof size.

    **5.** We skipped one thing: the verifier's "final check" uses `c_final` from the proof, but in real Jolt, C(r1,r2) is computed from the committed polynomials via a PCS opening proof (Hyrax). Why can't we just trust the prover's claimed value?

    > Because the prover could lie. If we accept `c_final` from the prover without proof, they can set it to whatever makes the sumcheck pass, even for an invalid trace. The **polynomial commitment scheme** (PCS) binds the prover: they committed to the polynomials at the start, and the opening proof (Hyrax) proves that `C(r1, r2)` is consistent with those commitments. The verifier doesn't trust the value, they verify it against the commitment. This is Stage 8 of Jolt, using Hyrax over Grumpkin for efficient in-circuit MSMs.
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
