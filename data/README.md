# Input data

The supplied CSVs are organized by role without changing their contents:

- `processed/students/`: retained source-anchor profiles.
- `processed/splits/`: fixed source split assignments.
- `synthetic/populations/`: supplied synthetic fixture.
- `synthetic/simulator_states/`: assumed hidden reset parameters and diagnostics.
- `external/`: historical reference outcomes, higher-education tables and dictionary.

Load through `src.data.dataset` or the consumer stores. Their default directory is
this data root. Custom flat directories of CSV files remain supported. Reference
outcomes and hidden parameters must not be used as policy features. Never overwrite
inputs in notebook cells; export derived work under `results/`.
