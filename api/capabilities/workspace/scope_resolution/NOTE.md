# CMO Chat Scope Note

Brand scope is not a hard lock.

CMO chat can discuss, compare, and switch between Brands naturally. Artifact execution is stricter: every generated artifact must have exactly one execution Brand.

The CMO must emit a hidden `SCOPE:` block on every turn:

```text
SCOPE:
conversation_brand: <Brand name or none>
execution_brand: <Brand name or none>
mode: <discussion|switch|comparison|new_artifact|equivalent_artifact|clarify>
confidence: <high|medium|low>
```

BOS code validates this block. Code does not decide brand switching with platform or phrase routing. It only resolves Brand names to IDs, blocks unowned artifact runs, passes `brand_id` into module execution, and keeps cross-brand facts out of artifacts.
