import React from 'react';

const DarkTraceLogo = ({ size = 44, className = '' }) => (
  <svg
    className={`darktrace-logo ${className}`.trim()}
    width={size}
    height={size}
    viewBox="0 0 64 64"
    role="img"
    aria-label="DarkTrace logo"
  >
    <defs>
      <linearGradient id="darktraceShield" x1="10" y1="8" x2="56" y2="58" gradientUnits="userSpaceOnUse">
        <stop offset="0" stopColor="#22d3ee" />
        <stop offset="0.52" stopColor="#7c3aed" />
        <stop offset="1" stopColor="#f43f5e" />
      </linearGradient>
      <linearGradient id="darktraceTrace" x1="16" y1="42" x2="50" y2="18" gradientUnits="userSpaceOnUse">
        <stop offset="0" stopColor="#fbbf24" />
        <stop offset="1" stopColor="#2dd4bf" />
      </linearGradient>
    </defs>

    <path
      d="M32 5 55 14v17c0 14.5-9.4 23.4-23 28-13.6-4.6-23-13.5-23-28V14L32 5Z"
      fill="url(#darktraceShield)"
    />
    <path
      d="M32 10.6 49.4 17.4v13.2c0 10.8-6.6 17.9-17.4 22-10.8-4.1-17.4-11.2-17.4-22V17.4L32 10.6Z"
      fill="#080b12"
      opacity="0.86"
    />
    <path
      d="M18 39.4h9.1l4.1-17.8 5.5 25.2 4.2-13.7H50"
      fill="none"
      stroke="url(#darktraceTrace)"
      strokeWidth="4"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M32 17v-6M32 53v-6M14 31h6M44 31h6"
      stroke="#7dd3fc"
      strokeWidth="2"
      strokeLinecap="round"
      opacity="0.75"
    />
  </svg>
);

export default DarkTraceLogo;
