// n8n's node loader uses the `n8n.nodes` block in package.json to find
// node files — but it first resolves the package via `main`, so we need
// at least an empty CommonJS module here to avoid a load failure.
module.exports = {};
