// Template narratives for offline results (no LLM available).
// Shown to users when the device has no server connection.
// Keys must exactly match CLASS_NAMES in src/lib/onnx.ts.
// Clinical language reviewed to be informative without being diagnostic.

const TEMPLATES: Record<string, string> = {
  demodicosis: `**Classification Result:** Demodicosis (Demodex mite infestation)

**Findings:** The image pattern is consistent with demodicosis, characterized by focal or generalized alopecia, erythema, and possible follicular plugging.

**Differential Considerations:** Bacterial pyoderma, dermatophytosis, and other follicular diseases should be considered.

**Recommended Next Steps:**
- Skin scraping (deep) to confirm Demodex mites
- Trichogram to assess hair follicle involvement
- Consult a veterinarian for treatment protocol

*This is an automated classification result, not a diagnosis. Veterinary confirmation is required.*`,

  Dermatitis: `**Classification Result:** Dermatitis

**Findings:** The image pattern suggests an inflammatory skin condition with possible erythema, scaling, or crusting.

**Differential Considerations:** Allergic dermatitis, contact dermatitis, bacterial pyoderma, and autoimmune conditions should be considered.

**Recommended Next Steps:**
- Note any recent dietary changes or environmental exposures
- Document lesion distribution and progression
- Consult a veterinarian for differential workup

*This is an automated classification result, not a diagnosis. Veterinary confirmation is required.*`,

  Fungal_infections: `**Classification Result:** Fungal Infection

**Findings:** The image pattern is consistent with a fungal skin infection, possibly dermatophytosis (ringworm) or Malassezia dermatitis.

**Differential Considerations:** Bacterial pyoderma, demodicosis, and sebaceous adenitis should be considered.

**Recommended Next Steps:**
- Wood's lamp examination
- Fungal culture (DTM) for definitive identification
- Consult a veterinarian before initiating antifungal therapy

*This is an automated classification result, not a diagnosis. Veterinary confirmation is required.*`,

  Healthy: `**Classification Result:** Healthy Skin

**Findings:** No significant dermatological abnormalities detected in the image. The skin and coat appear within normal limits.

**Note:** If you are concerned about a specific area, try photographing it more closely with good lighting.

*This is an automated classification result. If symptoms persist, consult a veterinarian.*`,

  Hypersensitivity_Allergic_Dermatitis: `**Classification Result:** Hypersensitivity / Allergic Dermatitis

**Findings:** The image pattern suggests an allergic skin reaction, characterized by erythema, pruritus-related changes, or urticarial lesions.

**Differential Considerations:** Flea allergy dermatitis (FAD), atopic dermatitis, food allergy, and contact hypersensitivity should be considered.

**Recommended Next Steps:**
- Assess flea control status
- Consider elimination diet trial if food allergy suspected
- Consult a veterinarian for allergy workup and management

*This is an automated classification result, not a diagnosis. Veterinary confirmation is required.*`,

  ringworm: `**Classification Result:** Ringworm (Dermatophytosis)

**Findings:** The image pattern is consistent with dermatophytosis, characterized by circular or irregular areas of alopecia with scaling.

**Differential Considerations:** Bacterial pyoderma, demodicosis, and other causes of focal alopecia should be considered.

**Recommended Next Steps:**
- Wood's lamp examination (some Microsporum species fluoresce)
- Fungal culture for definitive diagnosis
- Isolate affected animal (ringworm is zoonotic — transmissible to humans)
- Consult a veterinarian before treatment

**Zoonotic Warning:** Ringworm can be transmitted to humans. Practice good hygiene and limit contact with affected areas.

*This is an automated classification result, not a diagnosis. Veterinary confirmation is required.*`,
};

const INCONCLUSIVE_TEMPLATE = `**Result: Inconclusive**

The image does not clearly match any of the conditions this system was trained to recognize. The possibilities listed below are the model's best guesses, but none reached a sufficient confidence level.

**Please consult a veterinarian for proper assessment.**

*This is an automated classification result with low confidence. Do not act on this information without professional guidance.*`;

const LOW_CONFIDENCE_PREFIX = `**Note: Low Confidence Classification**

The following assessment is based on a classification result with limited confidence. The model is uncertain — consider the differentials carefully and seek veterinary confirmation before any action.\n\n`;

export function getTemplateNarrative(
  label: string,
  prediction_quality: "confident" | "low_confidence" | "inconclusive" = "confident",
): string {
  if (prediction_quality === "inconclusive") {
    return INCONCLUSIVE_TEMPLATE;
  }

  const base =
    TEMPLATES[label] ??
    `**Classification Result:** ${label.replace(/_/g, " ")}

No detailed template available for this classification.

*This is an automated classification result, not a diagnosis. Consult a veterinarian.*`;

  if (prediction_quality === "low_confidence") {
    return LOW_CONFIDENCE_PREFIX + base;
  }

  return base;
}
