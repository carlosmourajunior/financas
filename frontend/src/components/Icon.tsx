const paths = {
  inicio: <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />,
  lista: <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />,
  cartao: (
    <>
      <rect x="2" y="5" width="20" height="14" rx="2" />
      <path d="M2 10h20" />
    </>
  ),
  importar: <path d="M12 16V4M7 9l5-5 5 5M4 20h16" />,
  mais: <path d="M12 5v14M5 12h14" />,
  olho: (
    <>
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  sino: <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10 21h4" />,
  direita: <path d="m9 6 6 6-6 6" />,
  esquerda: <path d="m15 6-6 6 6 6" />,
  fechar: <path d="M6 6l12 12M18 6 6 18" />,
  buscar: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </>
  ),
  emprestimo: <path d="M7 7h11l-3-3M17 17H6l3 3" />,
  arquivo: <path d="M14 3H6v18h12V7zM14 3v4h4M12 17v-6M9.5 13.5 12 11l2.5 2.5" />,
  camera: (
    <>
      <path d="M3 8h4l2-3h6l2 3h4v11H3z" />
      <circle cx="12" cy="13" r="3.5" />
    </>
  ),
}

export type IconName = keyof typeof paths

export default function Icon({ name, size = 22, strokeWidth = 1.8 }: { name: IconName; size?: number; strokeWidth?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  )
}
