# %% [markdown]
# # Hello cells
# Demo of `.py` cell-style notebook.
# Markdown cells start with `# %% [markdown]` and use `#` for content.
# Code cells start with `# %%`.

# %%
# First code cell. Runs as a unit.
# In VSCode: click "Run Cell" above this line, or Ctrl+Enter.
print("hello world")

# %%
# Second cell. Shares kernel state with the first.
x = 2 + 2
x  # last expression auto-displays in the interactive window — no print() needed

# %%
# Variables persist across cells.
greeting = "hello"
name = "owen"

# %%
f"{greeting}, {name}"

# %%
# DataFrame demo — what edgartools-style returns look like.
import pandas as pd

df = pd.DataFrame({
    "outlet": ["CBS", "NBC", "ABC"],
    "parent": ["Paramount", "Comcast", "Disney"],
})
df

# %%
# Series (one column).
df["parent"]

# %%
# Filter rows. Vectorized — no for-loop.
df[df["parent"] == "Comcast"]

# %%
