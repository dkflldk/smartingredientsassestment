const form = document.getElementById("recipe-form");
const input = document.getElementById("ingredients-input");
const inputError = document.getElementById("input-error");
const apiError = document.getElementById("api-error");
const loading = document.getElementById("loading");
const results = document.getElementById("results");
const submitBtn = document.getElementById("submit-btn");

function clearMessages() {
  inputError.hidden = true;
  apiError.hidden = true;
}

function showInputError(message) {
  inputError.textContent = message;
  inputError.hidden = false;
}

function showApiError(message) {
  apiError.textContent = message;
  apiError.hidden = false;
}

function el(tag, options = {}) {
  const node = document.createElement(tag);
  if (options.className) node.className = options.className;
  if (options.text !== undefined) node.textContent = options.text;
  return node;
}

// Builds each card with textContent (never innerHTML) so recipe text coming
// back from the LLM can never be interpreted as markup.
function buildRecipeCard(recipe) {
  const card = el("article", { className: "recipe-card" });

  card.appendChild(el("h2", { text: recipe.name }));
  card.appendChild(
    el("p", {
      className: "recipe-meta",
      text: `Cooking time: ${recipe.cooking_time_minutes} min`,
    })
  );

  card.appendChild(el("h3", { text: "Ingredients" }));
  const ingredientsList = el("ul");
  recipe.ingredients.forEach((item) => {
    ingredientsList.appendChild(el("li", { text: item }));
  });
  card.appendChild(ingredientsList);

  card.appendChild(el("h3", { text: "Instructions" }));
  const instructionsList = el("ol");
  recipe.instructions.forEach((step) => {
    instructionsList.appendChild(el("li", { text: step }));
  });
  card.appendChild(instructionsList);

  card.appendChild(el("h3", { text: "Nutrition (per serving)" }));
  const nutritionList = el("ul", { className: "nutrition-list" });
  const { nutrition } = recipe;
  nutritionList.appendChild(el("li", { text: `Calories: ${nutrition.calories}` }));
  nutritionList.appendChild(el("li", { text: `Protein: ${nutrition.protein_g} g` }));
  nutritionList.appendChild(el("li", { text: `Carbs: ${nutrition.carbs_g} g` }));
  card.appendChild(nutritionList);

  return card;
}

function renderRecipes(recipes) {
  results.innerHTML = "";
  recipes.forEach((recipe) => {
    results.appendChild(buildRecipeCard(recipe));
  });
}

function parseIngredients(rawText) {
  return rawText
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessages();
  results.innerHTML = "";

  const ingredients = parseIngredients(input.value);

  if (ingredients.length === 0) {
    showInputError("Please enter at least one ingredient.");
    input.focus();
    return;
  }

  submitBtn.disabled = true;
  loading.hidden = false;

  try {
    const response = await fetch("/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ingredients }),
    });

    let data;
    try {
      data = await response.json();
    } catch (parseErr) {
      throw new Error("The server sent back something unexpected. Please try again.");
    }

    if (!response.ok) {
      const message = data.error || "Something went wrong while generating recipes. Please try again.";
      if (response.status === 400) {
        // 400 = problem with what the user typed (empty, or not real food
        // ingredients) - surface it next to the textarea, not as a backend error.
        showInputError(message);
      } else {
        showApiError(message);
      }
      return;
    }

    if (!Array.isArray(data.recipes) || data.recipes.length === 0) {
      throw new Error("No recipes were returned. Please try different ingredients.");
    }

    renderRecipes(data.recipes);
  } catch (err) {
    if (err instanceof TypeError) {
      // fetch() throws TypeError on network failure (server down, no connection, etc.)
      showApiError("Couldn't reach the server. Check your connection and try again.");
    } else {
      showApiError(err.message);
    }
  } finally {
    submitBtn.disabled = false;
    loading.hidden = true;
  }
});
