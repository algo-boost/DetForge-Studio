/** Flow IR v2 — 树形工作流工具 */
const FlowTree = (() => {
    const IR_VERSION = 2;
    const CONTAINERS = new Set(['control.if', 'control.loop']);
    const BRANCHES = {
        'control.if': ['then', 'else'],
        'control.loop': ['body'],
    };

    function isContainer(node) {
        return node && CONTAINERS.has(node.type);
    }

    function branchKeys(node) {
        return BRANCHES[node?.type] || [];
    }

    function prepareNode(node) {
        if (!node?.type) return node;
        node.params = node.params || {};
        if (node.type === 'control.if') {
            node.then = node.then || [];
            node.else = node.else || [];
        }
        if (node.type === 'control.loop') {
            node.body = node.body || [];
            if (node.params.loop_mode === 'rules' && !Array.isArray(node.params.rules)) {
                node.params.rules = [];
            }
        }
        branchKeys(node).forEach(b => (node[b] || []).forEach(prepareNode));
        return node;
    }

    function prepareFlow(flow) {
        const f = flow?.nodes ? JSON.parse(JSON.stringify(flow)) : { version: IR_VERSION, nodes: [] };
        f.version = IR_VERSION;
        f.nodes = (f.nodes || []).map(n => prepareNode(n));
        return f;
    }

    function resolve(flow, path) {
        if (!path?.length) return null;
        const root = flow.nodes.find(n => n.id === path[0]);
        if (!root) return null;
        if (path.length === 1) {
            return { node: root, list: flow.nodes, index: flow.nodes.findIndex(n => n.id === path[0]), parent: null, branch: null };
        }
        let cur = root;
        let list = flow.nodes;
        let parent = null;
        let branch = null;
        for (let i = 1; i < path.length; i += 2) {
            branch = path[i];
            const cid = path[i + 1];
            parent = cur;
            list = cur[branch] || [];
            cur = list.find(n => n.id === cid);
            if (!cur) return null;
            if (i + 2 >= path.length) {
                return { node: cur, parent, branch, list, index: list.findIndex(n => n.id === cid) };
            }
        }
        return null;
    }

    function addNode(flow, createNode, opts = {}) {
        const node = createNode();
        if (!node) return null;
        if (opts.containerPath?.length && opts.branch) {
            const ctx = resolve(flow, opts.containerPath);
            if (!ctx?.node || !branchKeys(ctx.node).includes(opts.branch)) return null;
            ctx.node[opts.branch] = ctx.node[opts.branch] || [];
            ctx.node[opts.branch].push(node);
            return [...opts.containerPath, opts.branch, node.id];
        }
        const idx = opts.atIndex ?? flow.nodes.length;
        flow.nodes.splice(idx, 0, node);
        return [node.id];
    }

    function removeAt(flow, path) {
        const ctx = resolve(flow, path);
        if (!ctx) return [];
        ctx.list.splice(ctx.index, 1);
        const parentPath = path.length > 1 ? path.slice(0, -2) : [];
        return parentPath.length ? parentPath : (flow.nodes[0] ? [flow.nodes[0].id] : []);
    }

    function moveAt(flow, path, dir) {
        const ctx = resolve(flow, path);
        if (!ctx) return path;
        const j = ctx.index + dir;
        if (j < 0 || j >= ctx.list.length) return path;
        [ctx.list[ctx.index], ctx.list[j]] = [ctx.list[j], ctx.list[ctx.index]];
        return path;
    }

    function countNodes(flow) {
        let n = 0;
        function walk(nodes) {
            (nodes || []).forEach(node => {
                n++;
                branchKeys(node).forEach(b => walk(node[b]));
            });
        }
        walk(flow.nodes);
        return n;
    }

    return { IR_VERSION, isContainer, branchKeys, prepareFlow, prepareNode, resolve, addNode, removeAt, moveAt, countNodes };
})();

export default FlowTree;
