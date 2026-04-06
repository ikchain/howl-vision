-- Drug dosages and interactions for veterinary use.
-- Sources: Merck Veterinary Manual (open access), FDA/CVM public data.
-- All drug names stored lowercase for case-insensitive lookup.
-- IDEMPOTENT: Uses CREATE IF NOT EXISTS + ON CONFLICT DO NOTHING.
-- Safe to run on every startup — required by backend lifespan handler.

CREATE TABLE IF NOT EXISTS drug_dosages (
    id              SERIAL PRIMARY KEY,
    drug_name       TEXT NOT NULL,
    species         TEXT NOT NULL,
    route           TEXT NOT NULL,
    dose_mg_kg_min  NUMERIC(8,4),
    dose_mg_kg_max  NUMERIC(8,4),
    frequency_h     SMALLINT,
    max_duration_d  SMALLINT,
    notes           TEXT,
    source          TEXT NOT NULL,
    UNIQUE (drug_name, species, route)
);

CREATE INDEX IF NOT EXISTS idx_dosages_lookup ON drug_dosages (drug_name, species);

CREATE TABLE IF NOT EXISTS drug_interactions (
    id              SERIAL PRIMARY KEY,
    drug_a          TEXT NOT NULL,
    drug_b          TEXT NOT NULL,
    severity        TEXT NOT NULL
        CHECK (severity IN ('contraindicated', 'major', 'moderate', 'minor')),
    mechanism       TEXT,
    clinical_effect TEXT NOT NULL,
    management      TEXT,
    source          TEXT NOT NULL,
    CHECK (drug_a < drug_b),
    UNIQUE (drug_a, drug_b)
);

CREATE INDEX IF NOT EXISTS idx_interactions_lookup ON drug_interactions (drug_a, drug_b);

-- =============================================================================
-- SEED DATA — Common veterinary drugs
-- Sources: Merck Veterinary Manual, FDA/CVM approved labels
-- =============================================================================

INSERT INTO drug_dosages (drug_name, species, route, dose_mg_kg_min, dose_mg_kg_max, frequency_h, max_duration_d, notes, source) VALUES
-- NSAIDs
('meloxicam', 'dog', 'oral', 0.1, 0.2, 24, 14, 'Give with food. Initial dose 0.2, maintenance 0.1 mg/kg', 'Merck Veterinary Manual'),
('meloxicam', 'cat', 'oral', 0.025, 0.05, 24, 3, 'Single dose preferred in cats. Risk of renal toxicity with repeated dosing', 'Merck Veterinary Manual'),
('carprofen', 'dog', 'oral', 2.0, 4.4, 12, 14, 'Can be given as 4.4 mg/kg once daily or 2.2 mg/kg twice daily', 'Merck Veterinary Manual'),
('firocoxib', 'dog', 'oral', 5.0, 5.0, 24, NULL, 'COX-2 selective. Monitor hepatic function', 'FDA/CVM approved label'),

-- Antibiotics
('amoxicillin', 'dog', 'oral', 10.0, 20.0, 12, 14, 'Broad spectrum. Can combine with clavulanic acid', 'Merck Veterinary Manual'),
('amoxicillin', 'cat', 'oral', 10.0, 20.0, 12, 14, 'Same dosing as canine', 'Merck Veterinary Manual'),
('amoxicillin-clavulanate', 'dog', 'oral', 12.5, 25.0, 12, 14, 'Amoxicillin component dosing. Enhanced spectrum vs beta-lactamase producers', 'Merck Veterinary Manual'),
('amoxicillin-clavulanate', 'cat', 'oral', 12.5, 25.0, 12, 14, 'Same dosing as canine', 'Merck Veterinary Manual'),
('metronidazole', 'dog', 'oral', 10.0, 15.0, 12, 14, 'Effective against anaerobes and Giardia. Neurotoxicity at high doses', 'Merck Veterinary Manual'),
('metronidazole', 'cat', 'oral', 10.0, 15.0, 12, 7, 'Shorter duration in cats. Bitter taste, consider compounding', 'Merck Veterinary Manual'),
('enrofloxacin', 'dog', 'oral', 5.0, 20.0, 24, 14, 'Fluoroquinolone. Avoid in growing dogs (cartilage damage)', 'Merck Veterinary Manual'),
('enrofloxacin', 'cat', 'oral', 5.0, 5.0, 24, 14, 'Max 5 mg/kg in cats. Higher doses cause retinal degeneration', 'Merck Veterinary Manual'),
('doxycycline', 'dog', 'oral', 5.0, 10.0, 12, 28, 'Give with food to reduce GI upset. First-line for tick-borne diseases', 'Merck Veterinary Manual'),
('doxycycline', 'cat', 'oral', 5.0, 10.0, 12, 28, 'Effective for Mycoplasma, Chlamydia, Bartonella', 'Merck Veterinary Manual'),
('cephalexin', 'dog', 'oral', 15.0, 30.0, 12, 21, 'First-gen cephalosporin. Good for skin and soft tissue infections', 'Merck Veterinary Manual'),
('cephalexin', 'cat', 'oral', 15.0, 30.0, 12, 21, 'Same dosing as canine', 'Merck Veterinary Manual'),

-- Corticosteroids
('prednisolone', 'dog', 'oral', 0.5, 2.0, 12, NULL, 'Anti-inflammatory: 0.5-1 mg/kg. Immunosuppressive: 1-2 mg/kg. Taper gradually', 'Merck Veterinary Manual'),
('prednisolone', 'cat', 'oral', 1.0, 2.0, 12, NULL, 'Use prednisolone NOT prednisone in cats (poor hepatic conversion)', 'Merck Veterinary Manual'),
('dexamethasone', 'dog', 'iv', 0.1, 0.5, 24, 3, 'Emergency anti-inflammatory. 7x potency of prednisolone', 'Merck Veterinary Manual'),

-- Antiparasitics
('fenbendazole', 'dog', 'oral', 50.0, 50.0, 24, 3, 'Broad-spectrum anthelmintic. Safe wide margin', 'Merck Veterinary Manual'),
('fenbendazole', 'cat', 'oral', 50.0, 50.0, 24, 3, 'Same dosing as canine', 'Merck Veterinary Manual'),
('ivermectin', 'dog', 'oral', 0.006, 0.012, NULL, NULL, 'Heartworm prevention. AVOID in MDR1 mutant breeds (Collies)', 'Merck Veterinary Manual'),
('praziquantel', 'dog', 'oral', 5.0, 5.0, NULL, NULL, 'Single dose for cestodes. Can repeat in 2-3 weeks', 'Merck Veterinary Manual'),
('praziquantel', 'cat', 'oral', 5.0, 5.0, NULL, NULL, 'Single dose for cestodes', 'Merck Veterinary Manual'),

-- GI
('omeprazole', 'dog', 'oral', 0.5, 1.0, 24, 28, 'Proton pump inhibitor. Give 30 min before meals', 'Merck Veterinary Manual'),
('maropitant', 'dog', 'sc', 1.0, 1.0, 24, 5, 'Antiemetic (NK1 antagonist). Also has visceral analgesic properties', 'FDA/CVM approved label'),
('maropitant', 'cat', 'sc', 1.0, 1.0, 24, 5, 'Same dosing as canine', 'FDA/CVM approved label'),
('metoclopramide', 'dog', 'oral', 0.2, 0.5, 8, 7, 'Prokinetic + antiemetic. Avoid with GI obstruction', 'Merck Veterinary Manual'),

-- Cardiac
('enalapril', 'dog', 'oral', 0.5, 0.5, 12, NULL, 'ACE inhibitor for CHF. Monitor renal values', 'Merck Veterinary Manual'),
('pimobendan', 'dog', 'oral', 0.2, 0.3, 12, NULL, 'Positive inotrope + vasodilator. Give 1h before meals', 'FDA/CVM approved label'),
('furosemide', 'dog', 'oral', 1.0, 4.0, 12, NULL, 'Loop diuretic for CHF/pulmonary edema. Monitor electrolytes', 'Merck Veterinary Manual'),

-- Analgesics
('tramadol', 'dog', 'oral', 2.0, 5.0, 8, 7, 'Opioid analgesic. Less effective than previously thought in dogs', 'Merck Veterinary Manual'),
('gabapentin', 'dog', 'oral', 5.0, 10.0, 8, NULL, 'Neuropathic pain. Also useful as anxiolytic pre-visit', 'Merck Veterinary Manual'),
('gabapentin', 'cat', 'oral', 5.0, 10.0, 12, NULL, 'Common pre-visit anxiolytic at 50-100mg per cat', 'Merck Veterinary Manual'),

-- Antihistamines
('diphenhydramine', 'dog', 'oral', 2.0, 4.0, 8, NULL, 'Antihistamine. Causes sedation. Limited efficacy for atopy', 'Merck Veterinary Manual'),
('cetirizine', 'dog', 'oral', 1.0, 2.0, 24, NULL, 'Second-gen antihistamine. Less sedating', 'Merck Veterinary Manual'),

-- Antifungals
('itraconazole', 'dog', 'oral', 5.0, 10.0, 24, 30, 'Pulse therapy for dermatophytosis: 1 week on, 1 week off', 'Merck Veterinary Manual'),
('itraconazole', 'cat', 'oral', 5.0, 10.0, 24, 30, 'Same protocol as canine. Monitor hepatic function', 'Merck Veterinary Manual')

ON CONFLICT (drug_name, species, route) DO NOTHING;


INSERT INTO drug_interactions (drug_a, drug_b, severity, mechanism, clinical_effect, management, source) VALUES
-- NSAID-NSAID combinations
('aspirin', 'carprofen', 'contraindicated', 'Additive COX inhibition', 'Severe GI ulceration, renal failure, coagulopathy', 'Never combine NSAIDs. Wait 5-7 days washout between switching', 'Merck Veterinary Manual'),
('aspirin', 'meloxicam', 'contraindicated', 'Additive COX inhibition', 'Severe GI ulceration, renal failure', 'Never combine NSAIDs. Wait 5-7 days washout', 'Merck Veterinary Manual'),
('carprofen', 'meloxicam', 'contraindicated', 'Additive COX inhibition', 'Severe GI ulceration, renal failure', 'Never combine NSAIDs. Wait 3-5 days washout', 'Merck Veterinary Manual'),
('firocoxib', 'meloxicam', 'contraindicated', 'Additive COX inhibition', 'Severe GI ulceration, renal failure', 'Never combine NSAIDs', 'Merck Veterinary Manual'),

-- NSAID + Corticosteroid
('meloxicam', 'prednisolone', 'major', 'Both inhibit mucosal protection via different mechanisms', 'High risk of GI ulceration and hemorrhage', 'Avoid concurrent use. If necessary, add GI protectant (omeprazole)', 'Merck Veterinary Manual'),
('carprofen', 'prednisolone', 'major', 'Additive GI mucosal damage', 'High risk of GI ulceration and perforation', 'Avoid concurrent use. Taper corticosteroid before starting NSAID', 'Merck Veterinary Manual'),

-- Nephrotoxic combinations
('enrofloxacin', 'meloxicam', 'moderate', 'Both have renal elimination and potential nephrotoxicity', 'Increased risk of acute kidney injury', 'Monitor renal values. Ensure adequate hydration', 'Merck Veterinary Manual'),
('furosemide', 'meloxicam', 'moderate', 'NSAIDs reduce renal blood flow; furosemide depends on renal perfusion', 'Reduced diuretic efficacy, risk of renal injury', 'Monitor urine output and renal values closely', 'Merck Veterinary Manual'),

-- CNS depression
('gabapentin', 'tramadol', 'moderate', 'Additive CNS depression', 'Excessive sedation, respiratory depression', 'Reduce doses of both when combining. Monitor closely', 'Merck Veterinary Manual'),

-- Metronidazole interactions
('metronidazole', 'tramadol', 'moderate', 'Both cause CNS effects, metronidazole neurotoxic at high doses', 'Increased risk of seizures and neurologic signs', 'Use lower doses of metronidazole when combining', 'Merck Veterinary Manual'),

-- ACE inhibitor + diuretic
('enalapril', 'furosemide', 'moderate', 'Additive hypotension and renal perfusion reduction', 'Risk of hypotension and azotemia', 'Common combination in CHF but requires careful dose titration and renal monitoring', 'Merck Veterinary Manual'),

-- MDR1 / P-glycoprotein
('itraconazole', 'ivermectin', 'major', 'Itraconazole inhibits P-glycoprotein, increasing ivermectin CNS penetration', 'Ivermectin toxicity: ataxia, mydriasis, tremors, coma', 'Avoid combination especially in MDR1-mutant breeds', 'Merck Veterinary Manual'),

-- QT prolongation
('dexamethasone', 'enrofloxacin', 'moderate', 'Both can affect cardiac conduction', 'Potential QT prolongation', 'Monitor cardiac rhythm in predisposed patients', 'Merck Veterinary Manual'),

-- GI motility
('maropitant', 'metoclopramide', 'minor', 'Opposing effects on emetic pathways but different mechanisms', 'Unpredictable antiemetic efficacy', 'Choose one antiemetic based on cause of vomiting', 'Merck Veterinary Manual')

ON CONFLICT (drug_a, drug_b) DO NOTHING;
