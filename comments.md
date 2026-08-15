# Comments 
__Latest Commit__: afa4413

## Frontend revamp
The current frontend is very basic, looks like something from 2005. We need to completely revamp it to modernize it and make it more appealing.
Some comments about the frontend:
1. The content on the login page is too small. Make it bigger. It alsolooks strange whent it is located centrally.
2. On the today page: The `By Meal` section shows how many items were eaten in each meal, but not what items, make it so that when we hover over the `<n> items` text, it shows what items were eaten in that meal and how many calories they contain (this can be preloaded).
3. On the today page: `log a meal` is a key feature that will be regualrly used. It should be a prominent button, not a small hyperlink text.
4. When we click the `log a meal` button, it takes us to the entries page, where we have click the `log a meal` button again. This is redundent. Fix this.
5. When we log a meal, using the estimate a meal option, we can modify the ai generated values of nutrients. This is good, But when we upload a image that has multiple food items in it, we can only modify the number of calories in it. Do we calculate the nutrients in it as well, we should. And whe we do calculate it, the user should be able to modify the entries like they do for the single item flow. 
6. The `Clear` button only clears the entries in the macronutrients section, not the micronutrients section. fix this
7. The reports section is good, But we need to give the user more options. This includes allowing the user to select dates, alloing them to see charts for whichever nutrient they want to track. ie a chart similar to the calorie tracker, but the user can select dates and the type of nutrient that want to track. ALso allow them to overlay multiple lines (for diffirent nutrients) with lables.
8. In the import page, The `Browse...` and `No file selected` are on the same button (atleast it looks like it) seperate them

  