function PagePlaceholder({ title, description }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="text-center px-4">
        <h1 className="text-2xl font-semibold text-slate-800">{title}</h1>
        {description && <p className="mt-2 text-slate-500">{description}</p>}
      </div>
    </div>
  );
}

export default PagePlaceholder;
