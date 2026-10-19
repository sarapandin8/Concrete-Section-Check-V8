# SLAB.REVIEW57 — additional code references and interpretation

The coupled shell field, source transformations, conservative shear screens and main As requirements from CHECK56 are unchanged. This release adds independent conventional bending references and exposes each existing check's source. It does not validate a full combined 3D N–M–V model or complete bridge-deck design acceptance.

## Tension-mat RC strip reference

For each mat, use a 1,000 mm-wide singly reinforced strip of the recovered local slab thickness h. The effective depth is d = h − the actual corresponding mat centre cover. Do not credit opposite-mat strength. Compute the following in consistent N/mm units:

    a = As fy / (alpha1 fc b)
    c = a / beta1
    epsilon_t = 0.003(d/c − 1)
    Mr = 0.90 As fy(d − a/2)

As is the provided mat area per metre; b = 1,000 mm. Convert N·mm to kN·m by dividing by 1e6. Positive CSI direct moment demands bottom steel; negative demands top steel. The concurrent moment triplet is converted to conservative Wood–Armer values before the four mat comparisons, with the same sign convention as CHECK56.

Reuse the repository's AASHTO alpha1, beta1 and tension-control-limit functions. These use the code's ksi breakpoints even when project input is MPa. Use Mr only when the concrete/steel strength is in the documented range, the compression block fits and epsilon_t meets the applicable tension-control limit. This also establishes yielding for the stated normal rebar modulus assumption. Unqualified reference resistance remains NaN; no phi=0.90 credit is assigned to an over-reinforced/unsupported reference.

The reference is **N=0**. All three membrane components must be numerical zero within 1e-8 kN/m. That tolerance is numerical only and is not an engineering threshold for discarding demand. A nonzero Nx, Ny or Nxy leaves the reference D/C unavailable and the reference state REVIEW. The independent N=0 section property may still be displayed with its label; it is not used as resistance for that row's actual N–M demand. The existing coupled field handles those actions.

These are independent orthogonal strip references, not a shared two-direction concrete resistance domain. No complete shell acceptance is inferred from their ratios.

## Minimum-reinforcement sufficient screen

The supplied AASHTO 2020 Article 5.6.3.3 compares factored resistance to the lesser of the factored-moment branch and the cracking-moment branch. Therefore:

    Mr >= 1.33 Mu  implies  Mr >= min(1.33 Mu, Mcr)

For a qualified N=0 reference, 1.33 times the bending D/C is the sufficient-screen ratio. A passing ratio establishes this stronger branch within the reference's scope. Exceeding the ratio returns REVIEW, because the lesser Mcr branch might still satisfy the code. It is not reported as a minimum-reinforcement code failure.

The project does not supply every reinforcement standard/ultimate-strength detail required to choose the cracking factor. This milestone neither requests nor invents such data, and does not choose a grade from fy alone. It deliberately leaves the Mcr branch and combined-NM minimum qualification open. The sufficient-screen demand does not inflate the primary As requirement or replace the coupled source vector.

## Governing mechanisms

The primary field utilization is unchanged. Its numeric components are the four combined N–M/shear tie strength ratios, concrete compression, qualified one-way shear, shrinkage minimum and maximum spacing. A non-finite shear check remains REVIEW.

The new controlling-check label takes the maximum of those numeric components. Steel strength rows exclude shrinkage, which has its own row; a zero-action section controlled by minimum steel is therefore identified as minimum steel rather than a tensile-strength exceedance. The original four-mat table still includes the required shrinkage steel in As required.

The all-case breakdown takes each mechanism's maximum from one actual source record and records its LC / step / element / joint. It counts unique exceeded elements and unique elements with unresolved checks separately. An element can appear in both counts when one imported row exceeds and another is unresolved. Source-record maxima are not recombined into a synthetic vector.

The trace's ledger uses the single source record currently shown, and separates TNM/phi_s from the nominal additional shear-tie force. Its tie-driver description indicates which contribution is larger, not an independent final-design failure mechanism. If a reference view has no qualified record, the trace shows the governing coupled record for the selected case and explicitly states why the reference is unavailable.

## Maps and exports

The two reference views reuse the existing plan-map geometry and element-envelope policy. Unavailable reference values are grey, never zero. With no qualified numeric values the numeric color scale and governing diamond are omitted. A minimum sufficient-screen exceedance is visibly described as REVIEW, because only the stronger branch has been tested.

There is still one visible graph and one Calculate action. View/case changes reuse the input-bound result. The all-case status and main As summary do not change with reference views. Both the element-envelope CSV and the new all-case check-summary CSV preserve exact source identities. No main results are persisted to Project JSON or substituted into girder Summary / Report.

## Independent examples

With h = 350 mm, fc = 35 MPa, As = 1,000 mm²/m, fy = 390 MPa and longitudinal centre cover = 64 mm, a = 13.109244 mm. The tension-controlled singly reinforced reference gives Mr = 98.085328 kN·m/m. Mu = 40 kN·m/m gives bending D/C = 0.407808 and sufficient minimum-screen D/C = 0.542385. The compressed mat's tensile demand is zero. The tests independently calculate these force-couple values for both signs and both directions.

Additional tests verify different physical covers, high-strength ksi breakpoints, concurrent twisting moments, nonzero membrane guards, over-reinforced reference rejection, no mutation of source/steel, grey reference maps, mechanism source identity, unique-element counts, zero-action minimum classification, Calculate-only controls and unchanged main As/field results.

## References

- AASHTO LRFD Bridge Design Specifications, Ninth Edition (2020), supplied Section 5: 5.5.4.2, 5.6.2.1, 5.6.2.2 and 5.6.3.3. The minimum equation was checked against PDF page 52 (printed 5-42).
- Existing repository AASHTO helper functions in concrete_pmm_pro/code_checks/aashto_lrfd.py.
- CHECK56 source and transformation basis remains documented in SLAB_CHECK56_METHOD.md.
