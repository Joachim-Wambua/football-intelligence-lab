
# Football Intelligence Lab — Development Guidelines

## Project architecture
- Streamlit is the research environment.
- FastAPI provides typed analytics endpoints.
- Next.js/TypeScript is the product frontend.
- Python owns all football metrics and model calculations.
- Never duplicate mathematical calculations in TypeScript.

## Educational code standards
This is both a production-oriented portfolio project and an
MSc-level football analytics learning environment.

Write clean, readable, teaching-oriented code.

For nontrivial functions and algorithms:
- Add a docstring explaining purpose, inputs, outputs, assumptions,
  mathematical ideas, and edge cases.
- Explain WHY important implementation choices are made.
- Place concise comments beside mathematical formulas,
  transformations, normalization, and model calculations.
- Reference the relevant football concept when applicable.
- Use meaningful variable names rather than cryptic abbreviations.
- Include a small numerical example in documentation when useful.
- Teach the associated football analytics and mathematical concepts through
  selected examples and readable tests demonstrating their behavior.
- Explain statistical limitations, bias, and data-quality concerns.

Avoid comments that merely repeat what obvious code already says.
Do not over-comment simple assignments or imports.

## Football analytics requirements
- Clearly define every metric and its denominator.
- Distinguish observed statistics from model estimates.
- Preserve missing data instead of silently replacing it with zero.
- Never invent event data or silently assume coordinate conventions.
- Document data provenance and methodological limitations.
- Keep model training separate from API request handling.

## Testing
- Add tests for normal cases, boundary values, missing data,
  invalid inputs, and football-specific edge cases.
- Use small synthetic examples to demonstrate mathematical correctness.
- Include mathematical boundary cases and explicit missing-data semantics.
- Maintain the existing Python and frontend test suites.

## Documentation and explanations
For each substantial implementation:
1. Explain the football question being answered.
2. Explain the underlying mathematical or statistical approach.
3. Describe the implementation and important design decisions.
4. Show how to run and verify the feature.
5. State its assumptions and limitations.

Prefer understandable, modular implementations over unnecessarily
complex abstractions.
