# Prompt 1

Currently, CommitData handles a list of FileData concurrently. However...
- Each FileData first calls the loader for the file type, which in turn may call image-to-text-callbacks for any images.
  These are the binary document loader in text.py, and the PDF loader in pdf.py.
  The loaders currently work sequentially, calling the AI vision function of after each other, then joining the image text with the regular document text.
  Split this logic to make a list of AI vision call requests, then parallelize these, too.
  Then join the results with the regular document text.
- Each FileData then iterates over a list of chunks, each requiring a call to ai.embed. Parallelize this, too.
- This approach will fix the issue that, right now, the progress is only updated from the final FileData embedding loop; currently, everything happening before that is showing 0% for most of the runtime.

Plan to proceed in a multi-step fashion, as outlined below. Reflect deeply on the optimal sequence and use extreme programming with small deltas, verifying the architecture implementation at each step.

(1) FileData
- 1.1 FileData.process() is already multithreaded. DONE
- 1.2 Make FileData accept an AiFactor so it can spawn AiManagers for the chunks itself, see next item.
- 1.3 Parallelize chunking loop.

(2) Split the loaders. Split load_() functions into loader.prepare(), loader.process(), loader.format().
- 2.1 Make loader.prepare() gather and return AI vision requests.
- 2.2 Execute AI vision requests in parallel.
- 2.3 Feed AI vision results back into loader.process().
- 2.4 Make loader.format() compile and return the final text.

Proceed with EXTREME caution. Do not implement yet, but reason deeply about the optimal implementation while NEVER EVER DESTROYING CURRENT FUNCTIONALITY, WHICH HAS BEEN VERIFIED TO WORK, BUT IS EXTREMELY BRITTLE.

# Prompt 2

Update the README to reflect the concurrency features.
