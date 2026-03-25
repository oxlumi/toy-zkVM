import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Exercise 4: Symbolic Execution

    **Goal**: Run the **same verifier code** twice, once with real numbers, once with symbols, and see how the symbolic run produces an expression tree (AST) that **is** the circuit.

    This is the core trick behind Jolt's transpilation pipeline.

    ## The idea in one sentence

    Instead of computing `3 * 5 = 15`, record `Mul(3, 5)` as a node in a tree. At the end, the tree describes every operation the verifier performed, which is exactly the circuit a Groth16 prover needs.

    ## Why this works

    The Jolt verifier is generic over its field type: `fn verify<F: Field>(...)`. For real verification, `F = Fr` (BN254 scalar field) and it computes actual numbers. For transpilation, `F = MleAst` (symbolic type) and it records operations.

    **Same code, different type parameter.** That's the entire trick.
    """)
    return


@app.cell
def _():
    P = 97

    def f_add(a, b):
        return (a + b) % P

    def f_sub(a, b):
        return (a - b) % P

    def f_mul(a, b):
        return (a * b) % P

    return (P,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 1: A concrete field element

    First, let's wrap F_97 in a class so we can swap it out later.
    This is the "real" field, it computes actual values.
    """)
    return


@app.cell
def _(P):
    class ConcreteField:
        """A real field element in F_97. Computes actual values."""

        def __init__(self, value):
            self.value = value % P

        def __add__(self, other):
            return ConcreteField((self.value + other.value) % P)

        def __sub__(self, other):
            return ConcreteField((self.value - other.value) % P)

        def __mul__(self, other):
            return ConcreteField((self.value * other.value) % P)

        def __eq__(self, other):
            return self.value == other.value

        def __repr__(self):
            return str(self.value)

    # Quick test
    _a = ConcreteField(3)
    _b = ConcreteField(5)
    _c = _a * _b
    print(f"ConcreteField: {_a} * {_b} = {_c}")
    assert _c == ConcreteField(15)
    return (ConcreteField,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 2: A symbolic field element

    Now the magic. `SymbolicField` has the **same interface** as `ConcreteField`
    (add, sub, mul, eq), but instead of computing values, it builds an **expression tree**.

    ### The arena

    All nodes live in a single global list called the **arena**. A `SymbolicField` value
    is just an integer index (a `node_id`) pointing into this list. It doesn't hold the
    expression itself, it's lightweight, like a pointer.

    When we create a variable:
    ```
    a = SymbolicField(("Var", "left"))   # appends to arena, a.node_id = 0
    b = SymbolicField(("Var", "right"))  # appends to arena, b.node_id = 1
    ```

    The arena now looks like:
    ```
    arena[0] = ("Var", "left")
    arena[1] = ("Var", "right")
    ```

    ### Operations grow the tree

    When we do `c = a + b`, it doesn't compute anything. It creates a new node that **references** the two children by their indices:

    ```
    c = a + b   # appends ("Add", 0, 1) to arena, c.node_id = 2
    ```

    Arena:
    ```
    arena[0] = ("Var", "left")      <- leaf
    arena[1] = ("Var", "right")     <- leaf
    arena[2] = ("Add", 0, 1)        <- points back to nodes 0 and 1
    ```

    Operations can chain:
    ```
    d = c * a   # appends ("Mul", 2, 0) to arena, d.node_id = 3
    ```

    Arena:
    ```
    arena[0] = ("Var", "left")
    arena[1] = ("Var", "right")
    arena[2] = ("Add", 0, 1)        <- left + right
    arena[3] = ("Mul", 2, 0)        <- (left + right) * left
    ```

    This is a **DAG** (directed acyclic graph). Node 0 is referenced by both node 2 and node 3, that's sharing. In Jolt's real arena (millions of nodes), this sharing is relevant for efficiency (CSE = common subexpression elimination).

    ### Equality captures constraints

    The `==` operator is special. Instead of comparing values, it records a **constraint**:

    ```
    assert d == e    # creates Sub(d, e), appends its node_id to constraints list
    ```

    It also returns `True` unconditionally, so the verifier code doesn't stop at the assertion. The constraint says "this expression must equal zero", which becomes `api.AssertIsEqual(node, 0)` in the generated gnark circuit.

    In Jolt, this is how `MleAst::eq` works: when in "constraint mode", it captures
    the equality check instead of evaluating it.
    """)
    return


@app.cell
def _():
    # Global arena, all nodes live here
    arena = []
    # Constraints captured during symbolic execution
    constraints = []

    class SymbolicField:
        """
        A symbolic field element. Records operations as tree nodes
        instead of computing values.

        Each SymbolicField is just an index into the global arena.
        (In Jolt, this is MleAst with a NodeId.)
        """

        def __init__(self, node):
            """node is either a leaf or will be added to the arena."""
            arena.append(node)
            self.node_id = len(arena) - 1

        def __add__(self, other):
            return SymbolicField(("Add", self.node_id, other.node_id))

        def __sub__(self, other):
            return SymbolicField(("Sub", self.node_id, other.node_id))

        def __mul__(self, other):
            return SymbolicField(("Mul", self.node_id, other.node_id))

        def __eq__(self, other):
            # Instead of comparing values, CAPTURE a constraint!
            _diff = self - other
            constraints.append(_diff.node_id)
            # Return True so the verifier code keeps running
            # (just like Jolt's MleAst::eq returns true in constraint mode)
            return True

        def __repr__(self):
            return f"Node#{self.node_id}"

    return SymbolicField, arena, constraints


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 3: Same code, two behaviors

    Here's a tiny "verifier" function. It checks: does `left * right == expected`?

    Watch what happens when we call it with `ConcreteField` vs `SymbolicField`:
    """)
    return


@app.cell
def _(ConcreteField, SymbolicField, arena, constraints):
    def verify_multiplication(left, right, expected):
        """
        A tiny verifier: checks that left * right == expected.
        This function doesn't know or care whether it's running
        with real numbers or symbols.
        """
        _result = left * right
        assert (
            _result == expected
        )  # concrete: checks value; symbolic: records constraint
        return _result

    # === Run 1: Concrete (real verification) ===
    print("=== CONCRETE RUN ===")
    _c_left = ConcreteField(3)
    _c_right = ConcreteField(5)
    _c_expected = ConcreteField(15)
    _c_result = verify_multiplication(_c_left, _c_right, _c_expected)
    print(f"  3 * 5 = {_c_result}")
    print(f"  Assertion passed (real check)")

    # === Run 2: Symbolic (transpilation) ===
    # Clear arena and constraints for a fresh symbolic run
    arena.clear()
    constraints.clear()

    print("\n=== SYMBOLIC RUN ===")
    _s_left = SymbolicField(("Var", "left"))  # Node#0
    _s_right = SymbolicField(("Var", "right"))  # Node#1
    _s_expected = SymbolicField(("Var", "expected"))  # Node#2
    _s_result = verify_multiplication(_s_left, _s_right, _s_expected)

    print(f"  Result: {_s_result}")
    print(f"  Arena has {len(arena)} nodes")
    print(f"  Constraints captured: {len(constraints)}")

    print("\n  Arena contents:")
    for _i, _node in enumerate(arena):
        print(f"    Node#{_i}: {_node}")

    print(f"\n  Constraint: Node#{constraints[0]} must equal 0")
    print(f"    (which is: {arena[constraints[0]]})")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## What just happened?

    The **same function** `verify_multiplication` ran twice:

    | Run | Field type | `left * right` does... | `== expected` does... |
    |-----|------------|------------------------|----------------------|
    | Concrete | `ConcreteField` | Computes `3 * 5 = 15` | Checks `15 == 15` -> True |
    | Symbolic | `SymbolicField` | Creates `("Mul", Node#0, Node#1)` -> Node#3 | Creates `("Sub", Node#3, Node#2)` -> constraint |

    The symbolic run produced:
    - **An expression tree** (the arena) describing every operation
    - **A constraint** saying `Mul(left, right) - expected = 0`

    This is similar to what Jolt's transpiler does. The expression tree **is** the gnark circuit. The constraints **are** the `api.AssertIsEqual()` calls.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 4: A bigger example -> the sumcheck verifier

    Let's symbolically execute a simplified version of the sumcheck verifier from Exercise 3. This is closer to what Jolt actually transpiles.

    The verifier receives:
    - Round polynomial evaluations (from the proof)
    - Computes challenges via hashing
    - Checks consistency

    We'll run it symbolically to capture the full circuit.
    """)
    return


@app.cell
def _(SymbolicField, arena, constraints):
    # Clear for a fresh run
    arena.clear()
    constraints.clear()

    # --- Create symbolic variables for the proof data ---
    # These are the "witness" — values the prover provides
    # In real Jolt, these come from symbolize_proof()

    # Round 1: 4 evaluations of s1 (degree-3 polynomial)
    s1_0 = SymbolicField(("Var", "s1_eval_0"))  # Node#0
    s1_1 = SymbolicField(("Var", "s1_eval_1"))  # Node#1
    s1_2 = SymbolicField(("Var", "s1_eval_2"))  # Node#2
    s1_3 = SymbolicField(("Var", "s1_eval_3"))  # Node#3

    # Round 2: 4 evaluations of s2
    s2_0 = SymbolicField(("Var", "s2_eval_0"))  # Node#4
    s2_1 = SymbolicField(("Var", "s2_eval_1"))  # Node#5
    s2_2 = SymbolicField(("Var", "s2_eval_2"))  # Node#6
    s2_3 = SymbolicField(("Var", "s2_eval_3"))  # Node#7

    # The final evaluation C(r1, r2) — also provided by the prover
    c_final = SymbolicField(("Var", "c_final"))  # Node#8

    print(f"Created {len(arena)} symbolic variables (the witness)")
    return c_final, s1_0, s1_1, s2_0, s2_1


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Now let's run the verifier checks symbolically. Each `==` will capture a constraint.
    We'll simplify and use a fixed "hash" for challenges (in reality, this would
    be a symbolic Poseidon computation, adding more nodes to the arena).
    """)
    return


@app.cell
def _(SymbolicField, arena, c_final, constraints, s1_0, s1_1, s2_0, s2_1):
    # --- Symbolic verifier execution ---

    # For simplicity, we'll use concrete challenges here.
    # In real Jolt, these would be symbolic Poseidon outputs (adding hundreds
    # of nodes to the arena). The structure is the same.

    # ====== CONSTRAINT 1: Round 1 consistency ======
    # s1(0) + s1(1) should equal 0 (the claimed sum)
    _round1_sum = s1_0 + s1_1
    _zero = SymbolicField(("Const", 0))
    assert _round1_sum == _zero  # CAPTURES constraint!

    print(f"After constraint 1 (round 1 check):")
    print(f"  Arena size: {len(arena)} nodes")
    print(f"  Constraints: {len(constraints)}")

    # ====== CONSTRAINT 2: Round 2 consistency ======
    # s2(0) + s2(1) should equal s1(r1)
    # (In reality, s1(r1) would be computed via Lagrange interpolation
    #  over s1_0..s1_3, adding many nodes. We'll skip that for clarity.)
    _round2_sum = s2_0 + s2_1
    _s1_at_r1 = SymbolicField(("Var", "s1_at_r1"))  # placeholder
    assert _round2_sum == _s1_at_r1  # CAPTURES constraint!

    print(f"\nAfter constraint 2 (round 2 check):")
    print(f"  Arena size: {len(arena)} nodes")
    print(f"  Constraints: {len(constraints)}")

    # ====== CONSTRAINT 3: Final evaluation ======
    # s2(r2) should equal C(r1, r2)
    _s2_at_r2 = SymbolicField(("Var", "s2_at_r2"))  # placeholder
    assert _s2_at_r2 == c_final  # CAPTURES constraint!

    print(f"\nAfter constraint 3 (final check):")
    print(f"  Arena size: {len(arena)} nodes")
    print(f"  Constraints: {len(constraints)}")

    # --- Print the full arena ---
    print(f"\n{'=' * 50}")
    print(f"FULL ARENA ({len(arena)} nodes):")
    print(f"{'=' * 50}")
    for _i, _node in enumerate(arena):
        print(f"  Node#{_i:2d}: {_node}")

    print(f"\nCONSTRAINTS ({len(constraints)}):")
    for _i, _c in enumerate(constraints):
        print(f"  Constraint {_i}: Node#{_c} = 0")
        print(f"    which is: {arena[_c]}")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### The AST as a graph

    Let's visualize the arena as a DAG. Leaf nodes (variables and constants) are at the
    top, operations flow downward, and the red nodes at the bottom are the constraints
    (the expressions that must equal zero).
    """)
    return


@app.cell
def _(arena, constraints, mo):
    # Build a mermaid diagram from the arena
    _lines = ["graph TD"]

    # Style definitions
    _lines.append("    classDef var fill:#4a9eff,stroke:#2970c0,color:#fff")
    _lines.append("    classDef const fill:#7c7c7c,stroke:#555,color:#fff")
    _lines.append("    classDef op fill:#ffa64a,stroke:#c07020,color:#fff")
    _lines.append("    classDef constraint fill:#ff4a4a,stroke:#c02020,color:#fff")

    # Constraint node IDs for highlighting
    _constraint_set = set(constraints)

    for _i, _node in enumerate(arena):
        _op = _node[0]
        if _op == "Var":
            _label = _node[1]
            _lines.append(f'    N{_i}["{_label}"]:::var')
        elif _op == "Const":
            _lines.append(f'    N{_i}["{_node[1]}"]:::const')
        elif _op in ("Add", "Sub", "Mul"):
            if _i in _constraint_set:
                _lines.append(f'    N{_i}["{_op} = 0"]:::constraint')
            else:
                _lines.append(f'    N{_i}["{_op}"]:::op')
            _lines.append(f"    N{_node[1]} --> N{_i}")
            _lines.append(f"    N{_node[2]} --> N{_i}")

    _mermaid = "\n".join(_lines)
    mo.mermaid(_mermaid)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Each path from a blue variable node down to a red constraint node traces one
    chain of operations the verifier performs. The constraints are where the verifier
    says "this must be zero" -- those become `api.AssertIsEqual()` in gnark.

    Notice how some nodes feed into multiple downstream operations.
    That's the **sharing** that CSE exploits: compute it once, reuse the result.
    In Jolt's real arena with millions of nodes, this saves enormous amounts of work.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 5: From arena to circuit

    The arena **is** the circuit. Each node becomes a gnark API call:

    | Arena node | gnark code |
    |------------|------------|
    | `("Var", "s1_eval_0")` | `circuit.S1Eval0` (witness field) |
    | `("Const", 0)` | `frontend.Variable(0)` |
    | `("Add", 0, 1)` | `api.Add(circuit.S1Eval0, circuit.S1Eval1)` |
    | `("Sub", 3, 2)` | `api.Sub(node3, node2)` |
    | Constraint on Node#X | `api.AssertIsEqual(nodeX, 0)` |

    The transpiler walks the arena and emits Go code. That's the codegen step.
    Let's do it:
    """)
    return


@app.cell
def _(arena, constraints):
    def generate_circuit(arena_nodes, constraint_list):
        """
        Walk the arena and emit pseudocode for a gnark circuit.
        This is a simplified version of Jolt's gnark_codegen.rs.
        """
        _lines = []
        _lines.append("func (c *Circuit) Define(api frontend.API) error {")

        for _i, _node in enumerate(arena_nodes):
            _op = _node[0]
            if _op == "Var":
                _lines.append(f"    // node{_i} = circuit.{_node[1]}  (witness input)")
            elif _op == "Const":
                _lines.append(f"    node{_i} := frontend.Variable({_node[1]})")
            elif _op == "Add":
                _lines.append(
                    f"    node{_i} := api.Add(node{_node[1]}, node{_node[2]})"
                )
            elif _op == "Sub":
                _lines.append(
                    f"    node{_i} := api.Sub(node{_node[1]}, node{_node[2]})"
                )
            elif _op == "Mul":
                _lines.append(
                    f"    node{_i} := api.Mul(node{_node[1]}, node{_node[2]})"
                )

        _lines.append("")
        for _i, _c in enumerate(constraint_list):
            _lines.append(f"    api.AssertIsEqual(node{_c}, 0)  // constraint {_i}")

        _lines.append("    return nil")
        _lines.append("}")

        return "\n".join(_lines)

    _circuit_code = generate_circuit(list(arena), list(constraints))
    print("GENERATED CIRCUIT:")
    print("=" * 50)
    print(_circuit_code)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The full picture

    ```
    CONCRETE RUN (real verification)         SYMBOLIC RUN (transpilation)
    ─────────────────────────────────        ─────────────────────────────────
    s1_0 = 42                                s1_0 = SymbolicField("s1_eval_0")
    s1_1 = 55                                s1_1 = SymbolicField("s1_eval_1")

    sum = s1_0 + s1_1                        sum = s1_0 + s1_1
       → 42 + 55 = 0 (mod 97)                  → creates Node("Add", #0, #1)

    assert sum == 0                          assert sum == 0
       → checks 0 == 0 → True                  → captures constraint: Add(#0,#1) - 0 = 0

    Result: "proof is valid"                 Result: arena + constraints = CIRCUIT
    ```

    **This is exactly what Jolt does.** The `TranspilableVerifier` runs the same
    verification code with `MleAst` instead of `Fr`. The arena accumulates millions
    of nodes. The 17 assertions become 17 constraints. The codegen walks the arena
    and emits `stages_circuit.go`.

    The witness values (42, 55, ...) go into `stages_witness.json`.
    The circuit structure (Add, Mul, Sub, ...) goes into `stages_circuit.go`.
    gnark compiles the circuit to R1CS, Groth16 proves it, and you get 164 bytes.

    ---

    ## How this maps to Jolt

    | Our toy | Jolt |
    |---------|------|
    | `SymbolicField` | `MleAst` |
    | `arena` (list) | `NODE_ARENA` (global `Vec<Node>`) |
    | `constraints` (list) | `take_constraints()` |
    | `node_id` (int) | `NodeId` (usize) |
    | `__eq__` captures constraint | `PartialEq::eq` in constraint mode |
    | `generate_circuit()` | `gnark_codegen::generate_circuit_from_bundle()` |
    | `("Var", "s1_eval_0")` | `Atom::Var(0)` |
    | `("Add", 0, 1)` | `Node::Add(Edge(0), Edge(1))` |
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---

    ## Exercises

    **1.** Add a `__neg__` method to `SymbolicField` that creates a `("Neg", node_id)` node. Then try `result = -s1_0` and check the arena.

    > Add this to the class:
    > ```python
    > def __neg__(self):
    >     return SymbolicField(("Neg", self.node_id))
    > ```
    > Then `-s1_0` creates a new node `("Neg", 0)` in the arena. The node references its single child by index, just like `Add` and `Mul` reference two children.

    **2.** Our `generate_circuit` doesn't do CSE (Common Subexpression Elimination). If `node5 = Add(node0, node1)` and both `node7` and `node9` reference `node5`, the code emits `node5` once and reuses it. But what if we had **inlined** the expression instead? How many times would `Add(node0, node1)` appear?

    > **Twice** — once inside `node7` and once inside `node9`. Without the arena's sharing, every reference becomes a full copy of the subtree. In Jolt's real circuit with millions of nodes, this would cause exponential blowup. The arena + CSE is what keeps the generated code linear in size. Jolt's codegen tracks reference counts: nodes used more than once get a named variable (`cse_0`, `cse_1`, ...), single-use nodes get inlined.

    **3.** In Jolt, the arena for fibonacci(50) has **millions** of nodes. The generated `stages_circuit.go` is 6MB. Why is it so large? *(Hint: each sumcheck round adds Poseidon hash nodes + polynomial evaluation nodes, and there are hundreds of rounds across 7 stages.)*

    > Each sumcheck round adds: ~250 nodes for Poseidon hashing (absorb coefficients + squeeze challenge) + polynomial evaluation nodes (multiply coefficients by powers of the challenge). Across 7 stages with ~100+ total rounds, that's 100 × (250 + evaluation nodes) = tens of thousands of nodes just for the transcript. Then add the constraint evaluation nodes, Lagrange interpolation, eq polynomial evaluations, and the batching logic. It adds up to millions of nodes, which emit as millions of `api.Add/Mul/Sub` calls in Go.

    **4.** Why does `__eq__` return `True` even for symbolic values? What would happen if it returned `False`? *(Hint: think about what the verifier code does after an `assert`.)*

    > The verifier code does `assert result == expected`. If `__eq__` returned `False`, Python would raise an `AssertionError` and the symbolic execution would **stop**. We'd never reach the later constraints. By returning `True`, we let the verifier code run to completion, capturing **all** 17 assertions. The actual equality check isn't lost — it's recorded as a constraint in the arena. Jolt's `MleAst::eq` does the same thing: returns `true` in constraint mode so `verify()` keeps running.

    **Next**: Exercise 5 puts everything together — trace, sumcheck, Fiat-Shamir, and symbolic execution — into one end-to-end pipeline.
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
