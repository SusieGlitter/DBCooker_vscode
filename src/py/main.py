import sys
import json
import argparse
import yaml
import time
import datetime

def main():
    # 1. Parse Arguments to get config file path
    parser = argparse.ArgumentParser(description='DBCooker Backend')
    parser.add_argument('--config', type=str, required=True, help='Path to the YAML configuration file')
    args = parser.parse_args()

    try:
        # 2. Read YAML Configuration
        config = {}
        with open(args.config, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        api_key = config.get('apiKey', '')
        timestamp = config.get('timestamp', '')

        # 3. Read JSON from Stdin
        input_str = sys.stdin.read()
        if not input_str:
            raise ValueError("No input received from stdin")
        
        req = json.loads(input_str)
        func_name = req.get('funcName', 'N/A')

        # 4. Core Logic (Moving the mock logic from Vue to Python)
        
        # Prepare the Code Attempts Data
        code_attempts_data = {
            "attempt1": {
                "mode": "Template Fill-in",
                "syntaxOK": True, 
                "compileOK": False, 
                "semanticOK": False,
                "error": "Compiler Error: Undefined function 'PARSE_TEXT' in scope. Use 'text_to_unit'.",
                "generatedFiles": [
                    {
                        "filename": "date_trunc_v1.c", 
                        "content": "#include <stdio.h>\n// This is an incorrect implementation (Attempt 1).\nint main(void) {\n  const char* unit = \"hour\";\n  if (unit == NULL) {\n    return 1; // Error\n  }\n  return 0;\n}"
                    }
                ]
            },
            "attempt2": {
                "mode": "Free Generation",
                "syntaxOK": True, 
                "compileOK": True, 
                "semanticOK": True,
                "error": "",
                "generatedFiles": [
                    {
                        "filename": "date_trunc_v2.c", 
                        "content": "#include <postgres.h>\n#include <utils/datetime.h>\n\n/* Function definition for date_trunc (Attempt 2 - Final) */\nDatum date_trunc(PG_FUNCTION_ARGS)\n{\n  // Get arguments\n  text *units = PG_GETARG_TEXT_PP(0);\n  TimestampTz timestamp = PG_GETARG_TIMESTAMPTZ(1);\n\n  // Check for null values\n  if (units == NULL) return (Datum)0;\n\n  // Core logic: Truncate the timestamp\n  TimestampTz result = call_date_trunc_core(timestamp, units);\n\n  // Return the result\n  PG_RETURN_TIMESTAMPTZ(result);\n}"
                    }
                ]
            }
        }

        # Build Workflow Items
        items = [
            {
                "id": "char",
                "type": "characterization",
                "data": {
                    "name": func_name, 
                    "components": [
                        { "name": "PG_GETARG_TEXT_PP", "deps": [] },
                        { "name": "normalize_units_for_truncation", "deps": [{"name": "downcase_identifier", "deps": []}]},
                        { "name": "date_math_core_engine", "deps": [] }
                    ]
                }
            },
            {
                "id": "pseudo",
                "type": "pseudo",
                "data": {
                    "items": {
                        "step1": {
                            "title": "Input Validation and Parsing",
                            "code": "IF input IS NOT VALID THEN\n  RAISE ERROR 'Invalid input unit';\nEND IF\nparsed_unit = PARSE_TEXT(input, 'unit');"
                        },
                        "step2": {
                            "title": "Timezone Handling", 
                            "code": "IF timezone_present THEN\n  ts = CONVERT_TO_UTC(ts, timezone);\nEND IF;"
                        }
                    }
                }
            }
        ]

        attempt_count = 0
        for key, attempt_data in code_attempts_data.items():
            attempt_count += 1
            items.append({
                "id": f"code_{attempt_count}",
                "type": "codeAttempt",
                "data": {
                    key: attempt_data
                }
            })
            
        # Build Results Item (Dynamic based on input testcases)
        testcases = req.get('testcases', [])
        results_data = {}
        for idx, tc in enumerate(testcases):
            # Simulation: every even index passes, odd index fails (just for demo variety)
            is_match = (idx % 2 == 0)
            expected = tc.get('expected', 'N/A')
            results_data[f"test_{idx}"] = {
                "testcase": tc.get('sql', 'N/A'),
                "expected": expected,
                "actual": expected if is_match else f"[{expected}] (Mismatch)"
            }

        items.append({
            "id": "res",
            "type": "results",
            "data": {
                "items": results_data
            }
        })

        # Build Response Object
        response = {
            "analysis": { 
                "loaded": True 
            },
            "workflow": {
                "items": items,
                "loaded": True
            },
            "logs": {
                "items": [
                    {
                        "timestamp": "09:00:00 AM",
                        "messages": ["Previous run log 1.", "Previous run log 2. (Success)"],
                        "isActive": False
                    },
                    {
                        "timestamp": datetime.datetime.now().strftime("%I:%M:%S %p"),
                        "messages": [
                            f"Pipeline started for function: {func_name}",
                            f"Configuration loaded (API Key: {'***' + api_key[-4:] if api_key and len(api_key)>4 else 'Not Set'})",
                            "Database Code Analysis completed.", 
                            "Characterization completed. (3 components found)", 
                            "Pseudo-code generated.", 
                            "Code Attempt 1 failed: Compile error.", 
                            "Code Attempt 2 succeeded: Final code generated.", 
                            "Results generated."
                        ],
                        "isActive": True 
                    }
                ],
                "loaded": True
            }
        }

        # 5. Output JSON to Stdout
        print(json.dumps(response), flush=True)

    except Exception as e:
        # Return error as JSON
        error_response = {
            "status": "error",
            "message": str(e)
        }
        # Print to stdout so the extension catches it as JSON result or just fails
        # But our extension logic catches stderr for failures. 
        # If we print to stdout, it's treated as success unless we exit 1.
        # Let's print to stderr for critical failures or return a specific error JSON.
        # Here we return a JSON that the frontend handles as an error type if needed, 
        # but the extension expects the whole output to be the result.
        # Let's just print the error structure.
        print(json.dumps({"error": str(e)}), flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()