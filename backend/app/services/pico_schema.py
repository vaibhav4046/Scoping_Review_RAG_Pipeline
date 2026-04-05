from pydantic import BaseModel, Field
from typing import List, Optional

# -------------------------------------------------------------------
# PICO Sub-Models: Breaking down the extraction into logical chunks
# -------------------------------------------------------------------

class Population(BaseModel):
    condition: str = Field(..., description="The primary disease, condition, or health status being studied.")
    sample_size: Optional[int] = Field(None, description="Total number of participants (N) in the trial.")
    age_range: Optional[str] = Field(None, description="Age range, median, or mean age of the participants.")
    key_demographics: Optional[List[str]] = Field(default_factory=list, description="Other notable demographics (e.g., gender ratio, geographical location).")

class Intervention(BaseModel):
    category: str = Field(..., description="Category of intervention (e.g., 'Drug', 'Surgical', 'Behavioral', 'Device').")
    name: str = Field(..., description="Specific name of the active treatment, drug, or procedure.")
    dosage_and_duration: Optional[str] = Field(None, description="Dosage amount, frequency, and total duration of the intervention.")

class Comparator(BaseModel):
    category: str = Field(..., description="Category of comparator (e.g., 'Placebo', 'Active Control', 'Standard of Care', 'None').")
    name: Optional[str] = Field(None, description="Specific name of the comparator treatment, if applicable.")

class Outcome(BaseModel):
    primary_endpoint: str = Field(..., description="The main metric or objective measured at the end of the study.")
    statistical_results: Optional[str] = Field(None, description="Key statistical findings (e.g., p-values, confidence intervals, hazard ratios).")
    adverse_events: Optional[List[str]] = Field(default_factory=list, description="Any reported side effects, toxicities, or negative outcomes.")

# -------------------------------------------------------------------
# Main Parent Model: The final JSON contract
# -------------------------------------------------------------------

class ClinicalTrialExtraction(BaseModel):
    """
    Master schema for extracting PICO (Population, Intervention, Comparator, Outcome)
    data from clinical trial text snippets.
    """
    paper_id: str = Field(..., description="Unique identifier or DOI of the paper being analyzed.")
    population: Population
    intervention: Intervention
    comparator: Comparator
    outcome: Outcome

# --- Example of how to test the schema definition ---
if __name__ == "__main__":
    # This prints the JSON schema that the LLM will see under the hood
    print(ClinicalTrialExtraction.model_json_schema())
