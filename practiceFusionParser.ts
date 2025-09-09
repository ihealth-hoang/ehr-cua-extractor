import type { IEhrParser, MedicationData, LabData, ICDCodeData, EhrDataType } from "./types";

export class PracticeFusionParser implements IEhrParser {

  /**
   * Although Practice Fusion itself doesn't purposefully embed its chart in multiple
   * frames, advertising and ancillary content can be loaded inside iframes.  The
   * parent DataParser broadcasts the extraction request to **every** frame, so we
   * need to decline the request when the required DOM element for the given data
   * type is not present in the current frame.  This prevents duplicate "success =
   * false" responses from clobbering the positive one coming from the real
   * document.
   */
  shouldExtractInCurrentFrame(dataType: EhrDataType): boolean {
    const dt = (dataType as string).toLowerCase();
    switch (dt) {
      case 'medications':
        // As with canParse, include detection for the print-preview medication table so that
        // extraction is attempted inside the relevant iframe but skipped elsewhere.
        return Boolean(
          document.querySelector('div[data-element="medication-summary-card"]') ||
          document.querySelector('div[data-element="print-medications__active"]') ||
          document.querySelector('div[data-element="print-medications__historical"]')
        );
      case 'labs':
        return Boolean(document.querySelector('div.box-margin-Blg-v2:has(h3[data-element^="test-name-"])'));
      case 'icdcodes':
        return Boolean(document.querySelector('div[data-element="diagnoses-summary-card"]'));
      default:
        return false;
    }
  }

  canParse(dataType: EhrDataType): boolean {
    const dt = (dataType as string).toLowerCase();
    switch (dt) {
      case 'medications':
        // Medication information can appear either in the regular summary card *or* inside the
        // print-preview iframe ("print-medications__active|historical").  Accept either so that
        // the correct frame performs extraction while others decline.
        return Boolean(
          document.querySelector('div[data-element="medication-summary-card"]') ||
          document.querySelector('div[data-element="print-medications__active"]') ||
          document.querySelector('div[data-element="print-medications__historical"]')
        );
      case 'labs':
        // Check for the presence of lab panel containers identified by their specific structure
        return Boolean(document.querySelector('div.box-margin-Blg-v2:has(h3[data-element^="test-name-"])'));
      case 'icdcodes':
        // Check for the main diagnoses summary card container
        return Boolean(document.querySelector('div[data-element="diagnoses-summary-card"]'));
      default:
        return false;
    }
  }

  extractMedications(): MedicationData[] {
    const medications: MedicationData[] = [];

    // ---------- Preferential branch: print-preview medication tables ----------
    const activePrint = document.querySelector('div[data-element="print-medications__active"]');
    const historicalPrint = document.querySelector('div[data-element="print-medications__historical"]');

    if (activePrint || historicalPrint) {
      console.log("Practice Fusion: Found print-preview medication tables, parsing those exclusively.");

      const parsePrintContainer = (container: Element, status: string) => {
        container.querySelectorAll('div[data-element^="medication-"]').forEach((row, idx) => {
          try {
            const nameEl = row.querySelector('div[data-element="medication-item-text"]');
            if (!nameEl) {
              console.warn(`Skipping print medication row ${idx + 1}: no name element.`);
              return;
            }

            const sigEl = row.querySelector('div[data-element="medication-item-sig"]');
            const drugText = (nameEl.textContent || "").trim();
            const sigText = (sigEl?.textContent || "").trim();

            // Attempt a lightweight extraction of amount & formulation from the medication text
            let amount = "";
            let type = "";
            const doseRegex = /(\d+(?:\.\d+)?\s*(?:MG|G|MCG|µG|%))/i;
            const doseMatch = drugText.match(doseRegex);
            if (doseMatch) {
              amount = doseMatch[1].trim();
              type = drugText.substring(doseMatch.index! + doseMatch[0].length).trim();
            }

            // Capture the start/stop dates text (if present) just for completeness
            const datesEl = row.querySelector('div[data-element="medication-item-dates"]');
            let encounterDate = "";
            let startDate = "";
            let endDate = "";

            if (datesEl) {
              const timeEls = Array.from(datesEl.querySelectorAll('time')) as HTMLTimeElement[];

              // Helper to safely extract a date string from a <time> element
              const extractDate = (el: HTMLTimeElement | undefined): string => {
                if (!el) return "";
                const text = (el.textContent || "").trim();
                if (text) return text;
                const fallback = (el.getAttribute('title') || el.getAttribute('datetime') || "").split('T')[0];
                return fallback.trim();
              };

              if (timeEls.length >= 2) {
                // Typical case: both start and end present (may be empty strings)
                startDate = extractDate(timeEls[0]);
                endDate = extractDate(timeEls[1]);
              } else if (timeEls.length === 1) {
                // Only one date present – decide whether it's a start or end date based on the list (Active vs Historical)
                const singleDate = extractDate(timeEls[0]);
                if (status.toLowerCase() === "active") {
                  // Active list: single date represents start date, no end date yet
                  startDate = singleDate;
                  endDate = "";
                } else {
                  // Historical list: single date represents end/stop date; start date not available
                  startDate = "N/A";
                  endDate = singleDate;
                }
              }

              // Final clean-up: if either remains empty string, explicitly set to "N/A" for consistency
              if (!startDate) startDate = "N/A";
              if (!endDate) endDate = "";

              // Build encounterDate consistently if either date is present
              if (startDate || endDate) {
                // Avoid adding a trailing dash when startDate is "N/A" and endDate is empty
                encounterDate = `${startDate}${startDate && endDate ? ' - ' : ''}${endDate}`.trim();
              }
            }

            medications.push({
              drugName: drugText,
              sig: sigText || "N/A",
              encounterDate,
              status,
              provider: "",
              type,
              amount,
              startDate,
              endDate,
            });
          } catch (e) {
            console.error(`Error parsing print medication row ${idx + 1}:`, e, row);
          }
        });
      };

      if (activePrint) parsePrintContainer(activePrint, "Active");
      if (historicalPrint) parsePrintContainer(historicalPrint, "Discontinued");

      console.log("Extracted Practice Fusion Medications (print preview):", medications);
      return medications;
    }

    // ---------- Fallback: summary medication card ----------
    const medCard = document.querySelector('div[data-element="medication-summary-card"]');

    if (!medCard) {
      if (!this.canParse('medications')) {
        console.log("Practice Fusion medication card not found, and canParse returned false.");
        return [];
      }
      throw new Error("Practice Fusion medication card (div[data-element='medication-summary-card']) not found and no print-preview table located, but canParse was true.");
    }

    // Select all list items within the card, including potentially historical ones if loaded.
    // The provided HTML only shows active ones, but this selector is more general.
    const listItems = medCard.querySelectorAll('ul.list > li[data-element^="medication-summary-list-item-"]');

    listItems.forEach((item, index) => {
      try {
        const nameElement = item.querySelector('a[data-element="medication-name"]');
        const drugName = nameElement?.textContent?.trim() || "";

        if (!drugName) {
          console.warn(`Skipping medication item ${index + 1}: No name found.`);
          return; // Skip this item if no name is found
        }

        // Extract other details (Dosage, Route, Form) which appear as text nodes
        let dosage = "";
        let route = "";
        let form = "";
        const childNodes = Array.from(item.childNodes);
        const textNodes = childNodes.filter(node => node.nodeType === Node.TEXT_NODE && node.textContent?.trim());
        
        // Assuming the order is consistent: Name (in <a>), Dosage, Route, Form
        if (textNodes.length >= 3) {
            dosage = textNodes[0].textContent?.trim() || "";
            route = textNodes[1].textContent?.trim() || "";
            form = textNodes[2].textContent?.trim() || "";
        } else {
            console.warn(`Could not parse dosage/route/form reliably for ${drugName}`);
            // Attempt to grab whatever text is available after the name link
            let remainingText = "";
            let foundNameElement = false;
            childNodes.forEach(node => {
                if (node === nameElement) {
                    foundNameElement = true;
                } else if (foundNameElement && node.nodeType === Node.TEXT_NODE) {
                    remainingText += (node.textContent || "").trim() + " ";
                }
            });
            // Simple split - may not be robust
            const parts = remainingText.trim().split(' ');
            dosage = parts[0] || ""; 
            route = parts[1] || "";
            form = parts.slice(2).join(' ') || "";
        }
        
        // Construct sig from the parts
        const sig = `${dosage} ${route} ${form}`.trim();

        // Determine status - check class list for active/historical if possible
        // The example only shows active-medication class
        const status = item.classList.contains('active-medication') ? "Active" : 
                       item.classList.contains('historical-medication') ? "Discontinued" : "Unknown"; // Assuming historical means discontinued

        const medication: MedicationData = {
          drugName,
          sig: sig || "N/A", // Use N/A if sig is empty
          encounterDate: "", // Not available in this snippet
          status,
          provider: "", // Not available in this snippet
          type: form, // Use form as type for now
          amount: dosage, // Use dosage as amount for now
          startDate: "",
          endDate: "",
        };
        medications.push(medication);

      } catch (e) {
        console.error(`Error parsing Practice Fusion medication item ${index + 1}:`, e, item);
      }
    });

    // Note: The user requested a specific string format like "Apixaban (Eliquis) 5 MG Oral Tablet".
    // This function returns structured MedicationData[].
    // The calling code (popup.tsx) will need to format this if the specific string is needed for the AI prompt.
    console.log("Extracted Practice Fusion Medications:", medications);
    return medications;
  }

  // Add lab conversion rules property below the class opening
  private readonly labConversionRules: Record<string, { convert: (v: number) => number; decimals?: number; newUnits?: string }> = {
    'CBC (INCLUDES DIFF/PLT) - ABSOLUTE NEUTROPHILS': { convert: (v) => v > 100 ? v / 1000 : v, decimals: 3 },
    'CBC (INCLUDES DIFF/PLT) - ABSOLUTE LYMPHOCYTES': { convert: (v) => v > 100 ? v / 1000 : v, decimals: 3 },
    'CBC (INCLUDES DIFF/PLT) - ABSOLUTE MONOCYTES': { convert: (v) => v > 50 ? v / 1000 : v, decimals: 3 },
    'CBC (INCLUDES DIFF/PLT) - ABSOLUTE EOSINOPHILS': { convert: (v) => v > 50 ? v / 1000 : v, decimals: 3 },
    'CBC (INCLUDES DIFF/PLT) - ABSOLUTE BASOPHILS': { convert: (v) => v > 20 ? v / 1000 : v, decimals: 3 }
  };

  // Add helper method applyLabConversions near other helpers, before extractLabs
  private applyLabConversions(lab: LabData): LabData {
    // Try to match any key that appears within the testName (case-insensitive)
    const upperName = lab.testName.toUpperCase();
    const ruleEntry = Object.entries(this.labConversionRules).find(([key]) => upperName.includes(key));
    if (!ruleEntry) return lab; // no conversion rule matched

    const [, rule] = ruleEntry;

    // Attempt to extract a numeric value from the result string (remove commas, keep sign/decimal)
    const numericMatch = lab.result.replace(/,/g, '').match(/-?\d+(?:\.\d+)?/);
    if (!numericMatch) return lab; // cannot parse numeric portion – leave unchanged

    const numericValue = parseFloat(numericMatch[0]);
    if (isNaN(numericValue)) return lab; // parsing failed

    try {
      let converted = rule.convert(numericValue);
      if (rule.decimals !== undefined) {
        converted = parseFloat(converted.toFixed(rule.decimals));
      }
      lab.result = converted.toString();
      if (rule.newUnits !== undefined) {
        lab.units = rule.newUnits;
      }
    } catch (err) {
      console.error('[PracticeFusionParser DEBUG] applyLabConversions: error converting value', err, lab);
    }

    return lab;
  }

  extractLabs(): LabData[] {
    const allLabData: LabData[] = [];
    // Selector for the container div of each lab panel
    const panelContainers = document.querySelectorAll('div.box-margin-Blg-v2:has(h3[data-element^="test-name-"])');

    if (panelContainers.length === 0) {
        if (!this.canParse('labs')) {
            console.log("Practice Fusion lab panels not found, and canParse returned false.");
            return [];
        }
        // If canParse was true but we find no panels, something might be wrong with the selector or page structure
        console.warn("Practice Fusion lab panels check passed but no panel containers found with selector.");
        return [];
    }

    panelContainers.forEach((panelContainer, panelIndex) => {
        const panelNameElement = panelContainer.querySelector('h3[data-element^="test-name-"]');
        const panelName = panelNameElement?.textContent?.trim() || `Unknown Panel ${panelIndex + 1}`;

        const observationRows = panelContainer.querySelectorAll('tr[data-element^="data-table-row-"]');

        if (observationRows.length === 0) {
            console.warn(`No observation rows found in panel: ${panelName}`);
            return; // Skip this panel if no rows found
        }

        observationRows.forEach((row, rowIndex) => {
            try {
                const testNameElement = row.querySelector('div[data-element="observation-name"]');
                const resultElement = row.querySelector('p[data-element="observation-value"]');
                const referenceElement = row.querySelector('span[data-element="reference-range"]');
                const unitsElement = row.querySelector('span[data-element="units-measure"]');
                const dateElement = row.querySelector('p[data-element="observation-date"]');
                const statusElement = row.querySelector('p[data-element="observation-status"]');
                const abnormalFlagElement = row.querySelector('p[data-element="abnormal-flag"]'); // Optional: captures high/low flags

                const testName = testNameElement?.textContent?.trim() || "";
                // Need to handle potential abnormal icon inside the result element
                let result = resultElement?.textContent?.trim() || "";
                if (resultElement?.querySelector('i[data-element="abnormal-icon"]')) {
                    // If icon exists, remove its text content (if any) - though it's likely empty
                    // More reliably, just get the text node content directly if possible
                    const resultTextNodes = Array.from(resultElement.childNodes).filter(node => node.nodeType === Node.TEXT_NODE);
                    result = resultTextNodes.map(n => n.textContent?.trim()).join('') || result; // Fallback to original text if no text nodes found
                }


                const referenceRange = referenceElement?.textContent?.trim() || "";
                const units = unitsElement?.textContent?.trim() || "";
                // Attempt to parse date, might need refinement based on actual formats
                let collectionDate = dateElement?.textContent?.trim() || "";
                // Simple standardization attempt (assuming MM/DD/YYYY HH:MM am/pm format)
                 try {
                    const dateMatch = collectionDate.match(/(\d{1,2}\/\d{1,2}\/\d{4})/);
                    if (dateMatch && dateMatch[1]) {
                        collectionDate = dateMatch[1]; // Extract just MM/DD/YYYY part for consistency
                    }
                 } catch (dateError) {
                     console.warn(`Could not parse date "${collectionDate}" for ${testName}`);
                 }


                let status = statusElement?.textContent?.trim() || "Completed"; // Default to Completed if empty
                if (status.toLowerCase() === 'not available') {
                    status = "Not Available"; // Standardize
                }
                 // Add abnormal flag info to status if present
                 if (abnormalFlagElement) {
                    const flagText = abnormalFlagElement.textContent?.trim();
                    status += flagText ? ` (${flagText})` : " (Abnormal)";
                 }


                // Only add if a test name was found
                if (testName) {
                    const labEntry: LabData = {
                        // Include panel name for context, useful for AI later
                        testName: `${panelName} - ${testName}`,
                        result: result,
                        referenceRange: referenceRange,
                        units: units,
                        collectionDate: collectionDate, // Date extracted from row
                        status: status,
                    };

                    console.log("test-debug labData", JSON.stringify(labEntry));

                    const convertedEntry = this.applyLabConversions(labEntry);
                    allLabData.push(convertedEntry);
                } else {
                    console.warn(`Skipping row ${rowIndex + 1} in panel ${panelName}: No test name found.`);
                }

            } catch(e) {
                console.error(`Error parsing lab row ${rowIndex + 1} in panel ${panelName}:`, e, row);
            }
        });
    });


    // Note: The user requested output like "WBC 7.0 11/16/2024".
    // This function returns structured LabData[]. The panel name is prepended to the test name.
    // Formatting for the AI prompt needs to happen in popup.tsx.
    console.log("Extracted Practice Fusion Lab Data:", allLabData);
    return allLabData;
  }

  extractICDCodes(): ICDCodeData[] {
    const icdCodes: ICDCodeData[] = [];
    const diagnosisCard = document.querySelector('div[data-element="diagnoses-summary-card"]');

    if (!diagnosisCard) {
      console.log("Practice Fusion diagnoses card not found. Returning empty array.");
      return [];
    }

    // Find all the diagnosis text elements within the card
    const diagnosisItems = diagnosisCard.querySelectorAll('div[data-element="diagnosis-item-text"]');

    diagnosisItems.forEach((item, index) => {
      const fullText = item.textContent?.trim() || "";
      if (!fullText) {
        console.warn(`Skipping ICD code item ${index + 1}: Empty text.`);
        return;
      }

      // Regex to capture code inside parentheses and the description after it
      const match = fullText.match(/\(([^)]+)\)\s*(.*)/);

      if (match && match[1] && match[2]) {
        const code = match[1].trim();
        const description = match[2].trim();

        const icdCode: ICDCodeData = {
          code: code,
          description: description,
          dateAdded: "", // Not available in this snippet
          provider: "", // Not available in this snippet
          status: "Active" // Assuming active unless specified otherwise; HTML doesn't show status here
        };
        icdCodes.push(icdCode);
      } else {
        console.warn(`Could not parse code and description from text: "${fullText}"`);
        // Optionally, add the full text as description if no code is found
        // icdCodes.push({ code: "", description: fullText, ... });
      }
    });

    // Note: The user requested output like "(126.99) Other pulmonary embolism..."
    // This function returns structured ICDCodeData[].
    // The calling code (popup.tsx) will need to format this if the specific string is needed for the AI prompt.
    console.log("Extracted Practice Fusion ICD Codes:", icdCodes);
    return icdCodes;
  }

  extractPatientName(): string {
    const nameElement = document.querySelector('.patient-info__column.patient-info__column--with-border.patient-info__name');
    if (!nameElement) {
      console.warn("Patient name element not found.");
      return "Unknown";
    }
    return nameElement.textContent?.trim() || "Unknown";
  }

  extractPatientDOB(): string {
    // Primary selector for DOB
    const dobElement = document.querySelector('[data-element="patient-ribbon-dob"]');
    if (dobElement) {
      return dobElement.textContent?.trim() || "Unknown";
    }

    // Fallback mechanism for narrow screens
    const dobContainer = document.querySelector('.patient-info__column.visible-xl');
    if (dobContainer) {
      const dobText = dobContainer.querySelector('span[data-element="patient-ribbon-dob"]');
      return dobText?.textContent?.trim() || "Unknown";
    }

    console.warn("Patient DOB element not found.");
    return "Unknown";
  }
}