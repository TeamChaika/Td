/**
 * MarkdownContent — безопасный рендеринг Markdown с санитайзом.
 * Использует react-markdown + rehype-sanitize для защиты от XSS.
 */
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';

interface MarkdownContentProps {
  content: string | null | undefined;
  className?: string;
}

export function MarkdownContent({ content, className }: MarkdownContentProps) {
  if (!content) {
    return (
      <p className="text-muted-foreground italic">
        Описание пока не добавлено.
      </p>
    );
  }

  return (
    <div
      className={`prose prose-invert max-w-none
        prose-headings:text-foreground prose-headings:font-semibold
        prose-h2:text-2xl prose-h2:mt-8 prose-h2:mb-4
        prose-h3:text-xl prose-h3:mt-6 prose-h3:mb-3
        prose-p:text-foreground/85 prose-p:leading-relaxed
        prose-a:text-[var(--brand,theme(colors.blue.400))]
        prose-a:underline prose-a:underline-offset-2
        prose-strong:text-foreground
        prose-blockquote:border-l-[var(--brand,theme(colors.blue.400))]
        prose-blockquote:bg-white/5 prose-blockquote:py-1 prose-blockquote:px-4
        prose-blockquote:rounded-r-md prose-blockquote:not-italic
        prose-li:text-foreground/85
        prose-code:bg-white/10 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded
        prose-code:text-sm prose-code:before:content-none prose-code:after:content-none
        ${className ?? ''}`}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}