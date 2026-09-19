# Scheduling

Compile independent subproblems into a DAG. Default to at most three concurrent workers. Spawn only when expected parallel benefit exceeds delegation overhead, context cost, and merge risk. Read-only workers may share the base repository. Every concurrent writer must have a dedicated branch/worktree, and predicted overlapping write sets must be serialized unless explicitly running competing-solution mode.
