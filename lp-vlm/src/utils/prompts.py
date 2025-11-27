ITEMS_IN_PLASTIC_BOX_VLM_PROMPT = """
                                    Analyze this image captured at a grocery checkout counter.
                                    Focus specifically on any grocery items that are stored **inside transparent plastic boxes or containers**.

                                    Your task:
                                    1. Identify the **item contained inside the plastic box** (e.g., peas, strawberries, salad, etc.).
                                    2. Estimate the **weight** or approximate amount (e.g., "200 grams") based on visible evidence.
                                    3. If multiple boxes contain the same item, count them and report the total count.

                                    Output format (strict JSON only), Dont use text or special characters in count field, Clearly mention the weight/quantity if visible, 
                                    else estimate with units like grams, kg, etc. Dont use any other text or explanation in weight fields other than numeric values with units:
                                    [
                                        {
                                        "item_name": "Name of the item (e.g., peas, salad mix)",
                                        "weight": "Estimated weight (e.g., 200 grams)",
                                        "count": 1
                                        }
                                    ]
}"""

             
APPLE_COLOR_VLM_PROMPT="""
                The shared screenshot is from a grocery store contains various fruits, Mostly apples
                Your task is to identify the fruit and determine its color.
                Output format (strict JSON only) — no additional text or explanation:
                [{"item_name": "Apple", "count": 1, "color": "Red"}]
                
                """

SODA_BOTTLES_SIZE_VLM_PROMPT ="""Analyze the given image carefully. Identify all bottles visible in the image.
                                For each bottle, determine:

                                item_name – e.g., "Soda bottle" or "Beer Bottle" or "Water Bottle"
                                
                                brand – the brand name visible on the label the specific drink type (Coke, Pepsi, etc.)


                                size – approximate size such as "small", "medium", or "large", or numeric size if printed (e.g., "500ml", "1L"), print the size as seen on the label if available and you are sure 100%

                                Return your answer strictly in JSON format as shown below — no additional text or explanation:
                                
                                {
                                "objects": [
                                    {
                                    "item_name": "Beer Bottle",
                                    "brand": "Heineken",
                                    "size": "large (1L)"
                                    }
                                ]
                                }"""
                                
                                
                                
BOTTLE_PRODUCT_VLM_PROMPT = """
                            Analyze this image/video frame to identify bottle products like ketchup, soda, sauce, or other liquid products.
                            
                            Your task:
                            1. Identify the **item type** (e.g., ketchup, soda, hot sauce, etc.)
                            2. Determine the **brand name** visible on the label
                            3. Extract the **size** from the label if visible (e.g., "500ml", "1L", "12oz")
                            4. Count the **quantity** of each identical product
                            
                            Special rules:
                            - If multiple identical bottles are present, count them accurately
                            - If size is not clearly visible, estimate as "small", "medium", or "large"
                            - If brand is not visible or unclear, leave brand_name empty
                            - Only include bottles with liquid/sauce products, not other containers
                            
                            Output format (strict JSON only):
                            {
                                "bottles": [
                                    {
                                        "item_name": "Ketchup",
                                        "brand_name": "Heinz",
                                        "size": "500ml",
                                        "quantity": 2
                                    }
                                ]
                            }
                            """
                            
COMMON_PROMPT = """
You are a vision-language assistant that analyzes grocery images and identifies the visible items in strict JSON format only. Try to be as specific as possible with item names.
Items could be fruits, vegetables, bottles (soda, water, etc.), items in plastic containers, etc. 
Rules:
1. For Fruits/vegetables: include color in name, Dont duplicate items in output, Add only once. example:
  [{"item_name": "Black Apple"}]

2. For Single bottle: include brand and size, example (Try to estimate the size in ml or Liter if possible):
  [{"item_name": "Coke Bottle 1L"]

3. For Multiple bottles, example: (Try to estimate the size in ml or Liter if possible)
  [{"item_name": "Coke Bottle 200ml"}, {"item_name": "Pepsi Bottle 2L"}]

4. For Items in plastic containers: zoom in and read from the label of the box. Try to be as accurate as possible, example:
  [{"item_name": "Peeled peas"}]

Return only valid JSON array. No additional text.
"""


AGENT_PROMPT = """
You are a smart grocery item name validator. You will receive a single item name generated by a grocery detection system. The item name might include volume formats (like "200ml", "1 liter", "2 liters", etc.).

Your job is to validate according to these rules:

We have following items in grocery store:
 - "Red Apple"
 - "Green Apple"
 - "Coca-Cola Bottle Small"
 - "Coca-Cola Bottle Large"
 - "Peeled Pomegranate"
 
There may be spelling mistakes or additional prepositions from above but the item should be same as above items. Compare the grocery item name with the valid items in the store and check if it matches any of them based on the size criteria defined below.

1) Size Validator for coca-cola bottles:
  - Below is the size of bottles available in the grocery store and mapped to three categories: Small, Medium, and Large.
  - Small: 200 ml, 250 ml, 300 ml
  - Medium: 500 ml, 600 ml, 750 ml, 1 liter
  - Large: 1.25 liter, 1.5 liter, 2 liter, 2.25 liter, 2.5 liter

2) Formatting:
  - The final output must be in JSON format with a single object (not an array)
  - Examples:
    * If input is "Coca-Cola Bottle 500 ml" then output is:
     [{"item_name": "Coca-Cola Bottle 500 ml", "match": true}]
    * If input is "Coca-Cola Bottle 3 liters" then output is:
     [{"item_name": "Coca-Cola Bottle 3 liters", "match": false}]
  - If the item name is valid according to the size validator, set "match" to true; otherwise, set it to false.
  - Return only a single JSON object in an array."""


