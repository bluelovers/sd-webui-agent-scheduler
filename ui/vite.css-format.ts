import type { Plugin } from 'vite';

/**
 * 在每個規則結束的 `}` 後插入換行，其餘維持壓縮內容（不加縮排、不加空白）。
 * 字串、轉義字元、`/* ... *​/` 註解內的 `}` 不視為規則結束。
 */
function splitCssRules(css: string): string {
    let out = '';
    let quote = '';
    let parenDepth = 0;
    let i = 0;

    while (i < css.length) {
        const ch = css[i];

        if (quote) {
            out += ch;
            if (ch === '\\') {
                out += css[i + 1] ?? '';
                i += 2;
                continue;
            }
            if (ch === quote) quote = '';
            i += 1;
            continue;
        }

        if (ch === '/' && css[i + 1] === '*') {
            const end = css.indexOf('*/', i + 2);
            const stop = end === -1 ? css.length : end + 2;
            out += css.slice(i, stop);
            i = stop;
            continue;
        }

        if (ch === '"' || ch === "'") {
            quote = ch;
            out += ch;
            i += 1;
            continue;
        }

        if (ch === '(') parenDepth += 1;
        if (ch === ')') parenDepth = Math.max(0, parenDepth - 1);

        out += ch;
        i += 1;

        if (ch === '}' && parenDepth === 0) out += '\n';
    }

    if (!out.endsWith('\n')) out += '\n';
    return out;
}

/**
 * 建置期 CSS 輸出插件：
 * 1. 保留壓縮（build.cssMinify），但在每個規則後分行，讓 git diff 可逐行比對。
 * 2. 額外輸出一份根目錄的 style.css（sd-webui 實際載入的路徑），
 *    原本的 javascript/*.css 照常保留。
 */
export function cssBuildOutput(): Plugin {
    return {
        name: 'agent-scheduler:css-output',
        enforce: 'post',
        generateBundle(_options, bundle) {
            for (const output of Object.values(bundle)) {
                if (output.type !== 'asset' || !output.fileName.endsWith('.css')) continue;

                const raw =
                    typeof output.source === 'string'
                        ? output.source
                        : Buffer.from(output.source).toString('utf8');
                const formatted = splitCssRules(raw);
                output.source = formatted;

                if (output.fileName !== 'style.css') {
                    this.emitFile({ type: 'asset', fileName: 'style.css', source: formatted });
                }
            }
        },
    };
}
